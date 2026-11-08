"""Bind a pre-execution macro proposal to one complete, diagnostic Fold Tops run."""
import json
import os
from pathlib import Path
import uuid

import numpy as np

from garment_observation_trace import GarmentObservationTrace, sha256_file


def write_once(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())


class FullRecoveryChain:
    def __init__(self, evidence, env, upstream):
        self.evidence, self.env = evidence, env
        self.output, self.trial_id = evidence.output, evidence.record["trial_id"]
        self.phase = "normal-first-sleeve"
        self.finished = False
        self.decision = None
        from pxr import Gf, UsdLux
        camera = env.env_camera.camera
        light = UsdLux.DomeLight.Define(env.world.stage, "/World/FullRecoveryEvidenceLight")
        light.CreateIntensityAttr(1000.0)
        eye, target = [0.0, 3.6, 3.2], [0.0, 0.5, 0.6]
        view = Gf.Matrix4d().SetLookAt(Gf.Vec3d(*eye), Gf.Vec3d(*target), Gf.Vec3d(0, 0, 1))
        rotation = view.GetInverse().ExtractRotationQuat()
        camera.set_world_pose(position=np.array(eye),
                              orientation=np.array([rotation.GetReal(), *rotation.GetImaginary()]),
                              camera_axes="usd")
        camera.set_focal_length(2.4)
        camera.set_horizontal_aperture(2.4)
        # Freeze the sensor before any folding command, then let the render product settle.
        for _ in range(12):
            env.world.step(render=True)
        rgba = np.asarray(camera.get_current_frame().get("rgba"))
        if rgba.ndim != 3 or rgba.shape[-1] != 4 or np.ptp(rgba[..., :3]) == 0:
            raise RuntimeError("Full recovery camera is uniform or missing; abort before folding")
        self.trace = GarmentObservationTrace(
            self.output, env.world, env.env_camera.camera,
            {"left": env.bimanual_dex.dexleft, "right": env.bimanual_dex.dexright}, self.trial_id)
        position, orientation = camera.get_world_pose()
        sources = dict(evidence.record["upstream_sha256"])
        for name in ("Env_Config/Robot/DexRight_Ur10e.py", "Env_StandAlone/BaseEnv.py",
                     "Env_Config/Camera/Recording_Camera.py"):
            path = upstream / name
            if path.is_file():
                sources[name] = sha256_file(path)
        wrapper_sources = {name: sha256_file(Path(__file__).with_name(name)) for name in
                           ("fold_recovery_chain.py", "fold_recovery_evidence.py",
                            "garment_observation_trace.py", "run_fold_local.py", "run_local.ps1")}
        initial_points = self.output / "initial-point-cloud.npz"
        np.savez_compressed(initial_points, points=env.garment_pcd)
        self.context = {
            "schema": "full-fold-continuation-context/1", "trial_id": self.trial_id,
            "target_definition": "fixed-controller-continuation/v1",
            "target": {"name": "upstream Fold Tops 88 percent region diagnostic proxy",
                       "minimum_ratio": 0.88, "quality_is_srs_acceptance": False,
                       "boundary_source": "upstream initial point cloud / GAM indices 554,1540,1014,1385",
                       "initial_point_cloud_sha256": sha256_file(initial_points)},
            "controller": {"upstream_sha256": sources, "wrapper_sha256": wrapper_sources,
                           "resume": "third left dense move, then right sleeve and bottom-top",
                           "macro_motion_sample_scale_m": 0.01,
                           "failed_ik_policy": "abort the run; do not continue or assign a negative label"},
            "camera": {"mode": "fixed explicitly aimed environment camera; no hand tracking",
                       "prim_path": camera.prim_path, "resolution_wh": list(camera.get_resolution()),
                       "dome_light_intensity": 1000.0, "warmup_physics_steps": 12,
                       "orientation_axes": "world (Camera.get_world_pose default)",
                       "look_at_target_world_m": target, "focal_length": 2.4, "horizontal_aperture": 2.4,
                       "position_world_m": np.asarray(position).tolist(),
                       "orientation_wxyz": np.asarray(orientation).tolist(),
                       "intrinsics_px": np.asarray(camera.get_intrinsics_matrix()).tolist(),
                       "world_to_ros_camera": np.asarray(camera.get_view_matrix_ros()).tolist()},
            "preprocessing": {"version": "garment_trace_intake rgb_grid/8 history/4",
                              "raw_rgb": "uint8 RGB, unresized; unique rendering timestamps",
                              "online_features": "RGB and named q/dq; no hidden mesh, injection or outcome"},
            "execution_profile": {"physics_dt_s": float(env.world.get_physics_dt()),
                                  "observation_interval_physics_steps": 3,
                                  "position_unit": "m", "coordinate_frame": "world",
                                  "joint_position_unit": "rad", "worker_threads": 4,
                                  "gpu_contact_patch_budget_each": 262144,
                                  "product_legality": None, "contact_limits_verified": False,
                                  "velocity_limits_verified": False},
            "budget": {"diagnostic_macro_attempts": 1, "retry_count": 0,
                       "extra_open_wait_steps": 45, "extra_close_wait_steps": 12,
                       "wait_semantics": "additional physics steps after upstream hand method returns",
                       "product_budget": None},
            "human_policy": "no interactive control in this headless script; abort on exception",
            "context_status": "author-frozen diagnostic configuration; independent acceptance pending",
        }
        write_once(self.output / "continuation-context.json", self.context)
        self.context_ref = "continuation-context.json#sha256=" + sha256_file(self.output / "continuation-context.json")
        self.trace.boundary(self.phase)
        original_step = env.world.step

        def step(*args, **kwargs):
            result = original_step(*args, **kwargs)
            if int(env.world.current_time_step_index) % 3 == 0:
                self.trace.observe(self.phase)
            return result

        env.world.step = step
        original_record, original_stop = env.record, env.stop_record

        def record(task_name, stage_index=1):
            self.phase = "upstream-stage-" + str(stage_index)
            self.trace.boundary(self.phase)
            return original_record(task_name, stage_index)

        def stop_record():
            result = original_stop()
            self.trace.boundary("upstream-stage-" + str(env.stage_index) + "-end")
            return result

        env.record, env.stop_record = record, stop_record
        for side, arm in self.trace.arms.items():
            controller = arm.get_articulation_controller()
            controller.apply_action = self.trace.wrap_apply(side, controller.apply_action, lambda: self.phase)

    def propose(self, pick, lift, orientation):
        if self.decision is not None:
            raise RuntimeError("Only one diagnostic macro is permitted")
        orientation = np.asarray(orientation, dtype=float)
        orientation = orientation / np.linalg.norm(orientation)
        retreat = np.asarray(lift) + np.array([0.0, 0.0, 0.05])
        proposal = {"schema": "recovery-macro-proposal/1", "kind": "release-retreat-regrasp-lift",
                    "trial_id": self.trial_id, "candidate_id": str(uuid.uuid4()),
                    "source_reference": "macro-proposal.json; generated before recovery dispatch",
                    "available_at": self.trace.clock(), "arm": "left", "coordinate_frame": "world",
                    "position_unit": "m", "retreat_world_m": retreat.tolist(),
                    "pick_world_m": np.asarray(pick).tolist(), "lift_world_m": np.asarray(lift).tolist(),
                    "orientation_wxyz": orientation.tolist(), "open_wait_steps": 45, "close_wait_steps": 12}
        write_once(self.output / "macro-proposal.json", proposal)
        persisted = self.trace.clock()
        self.phase = "recovery-decision"
        self.trace.boundary(self.phase)
        self.decision = {
            "schema": "full-fold-recovery-decision/1", "trial_id": self.trial_id,
            "lineage_group": self.trial_id, "decision_id": str(uuid.uuid4()),
            "candidate_id": proposal["candidate_id"], "decision_at": self.trace.clock(),
            "observation_id": self.trace.observations[-1]["observation_id"],
            "proposal_persisted_at": persisted,
            "candidate_spec_reference": "macro-proposal.json#sha256=" + sha256_file(self.output / "macro-proposal.json"),
            "continuation_context_reference": self.context_ref,
            "target_definition": "fixed-controller-continuation/v1",
            "candidate_available_before_decision": True,
            "diagnostic_budget_remaining_before": 1, "product_legality": None,
            "label_review_reference": None, "continuation_success": None,
        }
        write_once(self.output / "recovery-decision.json", self.decision)
        return proposal

    def operation(self, name, function, *, fail_on_false=False, wait_steps=0, requested=None):
        self.phase = "macro-" + name
        start = len(self.trace.actions)
        entry = {"operation": name, "begin": self.trace.clock(), "command_ids": [],
                 "candidate_id": self.decision["candidate_id"], "extra_wait_steps": wait_steps,
                 "requested": requested}
        self.evidence.record.setdefault("macro_execution", []).append(entry)
        try:
            result = function()
            entry["sdk_result"] = None if result is None else bool(result)
            if fail_on_false and not result:
                raise RuntimeError("Macro IK failed at " + name)
            for _ in range(wait_steps):
                self.env.step()
            return result
        finally:
            entry["end"] = self.trace.clock()
            entry["command_ids"] = [a["command_id"] for a in self.trace.actions[start:]]
            self.evidence.save()

    def finish(self):
        if self.finished:
            return
        self.finished = True
        self.phase = "final-evidence"
        self.trace.boundary(self.phase)
        if self.trace.pending_feedback:
            raise RuntimeError("Incomplete final action feedback")
        self.trace.save(self.evidence.record["injection"], scope="complete_fold_tops_diagnostic_recovery")
        self.evidence.record["chain"] = {
            "decision_reference": "recovery-decision.json", "trial_id": self.trial_id,
            "candidate_id": self.decision["candidate_id"] if self.decision else None,
            "trace_reference": "observation-trace.json", "context_reference": self.context_ref,
            "local_recovery_label": None, "srs_quality_label": None, "autonomous_success": None,
            "independent_review_status": "pending"}
        self.evidence.save()
        files = [{"file": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)}
                 for path in sorted(self.output.iterdir()) if path.is_file() and path.name != "manifest.json"]
        write_once(self.output / "manifest.json", {"trial_id": self.trial_id, "files": files})
