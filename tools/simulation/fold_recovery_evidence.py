"""Insert one diagnostic first-sleeve regrasp, then resume upstream Fold Tops."""
import hashlib
import json
import os
from pathlib import Path
import time
import uuid

import imageio.v2 as imageio
import numpy as np

TCLC_018_W0_M = 0.4749789486568581


class FoldRecoveryEvidence:
    def __init__(self, output, upstream, base_env):
        from Env_Config.Utils_Project import Position_Judge

        self.output = output / ("fold-recovery-" + str(uuid.uuid4()))
        self.output.mkdir(parents=True)
        self.started = time.monotonic_ns()
        self.closed_hand = os.environ.get("ROBOTICS_FOLD_RECOVERY_CONDITION") == "closed-hand-slip"
        self.capture_trace = os.environ.get("ROBOTICS_FOLD_RECOVERY_TRACE") == "1"
        self.lateral_offset_m = float(os.environ.get("ROBOTICS_REGRASP_LATERAL_OFFSET_M", "0"))
        if not abs(self.lateral_offset_m) <= 0.02:
            raise ValueError("Diagnostic regrasp offset must be within 0.02 m of the original pick")
        pinned = ("Env_StandAlone/Fold_Tops_Env.py", "Env_Config/Robot/DexLeft_Ur10e.py",
                  "Env_Config/Robot/BimanualDex_Ur10e.py", "Env_Config/Utils_Project/Position_Judge.py")
        self.record = {"trial_id": str(uuid.uuid4()), "garment": "TCLC_018",
                       "injection": ("zero_friction_closed_hand_translation" if self.closed_hand
                                     else "early_open_after_first_lift"), "dr02_label": None,
                       "candidate": "regrasp_near_original_pick", "product_legality": None,
                       "regrasp_lateral_offset_m": self.lateral_offset_m,
                       "resume_at": "upstream first-sleeve transfer, third left dense move",
                       "upstream_sha256": {name: hashlib.sha256((upstream / name).read_bytes()).hexdigest()
                                           for name in pinned},
                       "checkpoints": {}, "candidate_steps": [], "judgment": None}
        step = base_env.step
        judge = Position_Judge.judge_pcd
        self.attached = False

        def prepare(env, *args, **kwargs):
            if not self.attached and getattr(env, "garment_pcd", None) is not None:
                self.attach(env)
                self.attached = True
            return step(env, *args, **kwargs)

        def collect_judgment(pcd, boundary, threshold=0.1):
            success = bool(judge(pcd, boundary, threshold))
            x0, x1, y0, y1 = boundary
            inside = (pcd[:, 0] >= x0) & (pcd[:, 0] <= x1) & (pcd[:, 1] >= y0) & (pcd[:, 1] <= y1)
            self.record["judgment"] = {"upstream_success": success, "inside_count": int(inside.sum()),
                                       "point_count": len(pcd), "minimum_ratio": 1 - threshold,
                                       "boundary_world_xy_m": [float(value) for value in boundary]}
            np.savez_compressed(self.output / "final-point-cloud.npz", points=pcd)
            self.save()
            return success

        base_env.step = prepare
        Position_Judge.judge_pcd = collect_judgment

    def save(self):
        self.record["wall_elapsed_s"] = (time.monotonic_ns() - self.started) / 1e9
        (self.output / "full-fold-recovery.json").write_text(
            json.dumps(self.record, indent=2, allow_nan=False), encoding="utf-8")

    def snapshot(self, env, name):
        camera = env.env_camera.camera
        start = time.monotonic_ns()
        frame = camera.get_current_frame()
        rgba = np.asarray(frame.get("rgba"))
        entry = {"sim_step": int(env.world.current_time_step_index),
                 "sim_time_s": float(env.world.current_time),
                 "read_begin_monotonic_ns": start, "read_end_monotonic_ns": time.monotonic_ns(),
                 "image": None}
        if rgba.ndim == 3 and rgba.shape[2] == 4 and rgba.dtype == np.uint8:
            path = self.output / (name + ".png")
            imageio.imwrite(path, rgba[..., :3])
            entry.update(image=path.name, image_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                         rendering_time_s=float(frame["rendering_time"]))
        self.record["checkpoints"][name] = entry
        self.save()

    def attach(self, env):
        from pxr import Usd, UsdGeom

        robot = env.bimanual_dex
        left = robot.dexleft
        original = left.dense_step_action
        move_count = 0
        pick = None
        lift = None
        patch_ids = None
        tips = [env.world.stage.GetPrimAtPath(f"/World/DexLeft/{name}") for name in ("fftip", "thtip")]
        trace = None
        phase = "first_sleeve_prepare"
        if self.capture_trace:
            from garment_observation_trace import GarmentObservationTrace

            arms = {"left": left, "right": robot.dexright}
            trace = GarmentObservationTrace(self.output, env.world, env.env_camera.camera, arms,
                                            self.record["trial_id"], stored_size=(240, 180))
            controllers = {side: arm.get_articulation_controller() for side, arm in arms.items()}
            dispatch = {side: controller.apply_action for side, controller in controllers.items()}
            original_step = env.world.step
            original_hand = robot.set_both_hand_state
            trace.boundary(phase)

            def step_with_trace(*args, **kwargs):
                result = original_step(*args, **kwargs)
                trace.observe(phase)
                return result

            def hand_with_trace(left_hand_state="None", right_hand_state="None"):
                if phase == "first_sleeve_approach":
                    boundary("first_sleeve_grasp_" + left_hand_state)
                return original_hand(left_hand_state, right_hand_state)

            for side, controller in controllers.items():
                controller.apply_action = trace.wrap_apply(side, dispatch[side], lambda: phase)
            env.world.step = step_with_trace
            robot.set_both_hand_state = hand_with_trace

        def boundary(name):
            nonlocal phase
            phase = name
            if trace:
                trace.boundary(phase)

        def vertices():
            mesh = env.garment.garment_mesh
            points = np.asarray(mesh._get_points_pose())
            transform = UsdGeom.Xformable(mesh.prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
            return (np.column_stack((points, np.ones(len(points)))) @ np.asarray(transform))[:, :3]

        def checkpoint(name):
            self.snapshot(env, name)
            self.record["checkpoints"][name]["intended_patch_xyz_m"] = vertices()[patch_ids].mean(axis=0).tolist()

        def held_window():
            observations = []
            for index in range(8):
                if index:
                    for _ in range(3):
                        env.step()
                hand_proxy = np.asarray([UsdGeom.Xformable(tip).ComputeLocalToWorldTransform(
                    Usd.TimeCode.Default()).ExtractTranslation() for tip in tips]).mean(axis=0)
                patch = vertices()[patch_ids].mean(axis=0)
                observations.append({"sim_time_s": float(env.world.current_time),
                                     "patch_minus_tip_midpoint_m": (patch - hand_proxy).tolist(),
                                     "patch_world_m": patch.tolist()})
            return observations

        def attempt(label, operation):
            boundary(label)
            begin = int(env.world.current_time_step_index)
            result = operation()
            self.record["candidate_steps"].append({"operation": label, "begin_sim_step": begin,
                                                   "end_sim_step": int(env.world.current_time_step_index),
                                                   "sdk_result": None if result is None else bool(result)})
            self.save()
            return result

        def move(target_pos, target_ori=None, *args, **kwargs):
            nonlocal move_count, pick, lift, patch_ids
            move_count += 1
            if move_count == 1:
                boundary("first_sleeve_approach")
                pick = np.array(target_pos)
                patch_ids = np.argsort(np.linalg.norm(vertices()[:, :2] - pick[:2], axis=1))[:12]
                self.record["intended_patch_vertex_ids"] = patch_ids.tolist()
                self.record["pick_world_m"] = pick.tolist()
            elif move_count == 2:
                boundary("first_sleeve_lift")
                lift = np.array(target_pos)
            elif move_count == 3:
                self.record["lift_world_m"] = lift.tolist()
                self.record["fixed_transfer_world_m"] = np.asarray(target_pos).tolist()
                checkpoint("before-injection")
                if self.closed_hand:
                    self.record["before_disturbance"] = held_window()
                    material = env.garment.particle_material
                    friction = float(material.get_friction())
                    disturbed = lift + np.array([0.20, 0.10, 0.02])
                    self.record["disturbance"] = {"target_world_m": disturbed.tolist(), "sample_scale_m": 0.04,
                                                  "original_friction": friction, "friction": 0.0}
                    try:
                        material.set_friction(0.0)
                        attempt("closed-hand-translation", lambda: original(
                            disturbed, target_ori, *args, **kwargs, dense_sample_scale=0.04))
                        self.record["after_disturbance"] = held_window()
                    finally:
                        material.set_friction(friction)
                else:
                    attempt("injected-open", lambda: robot.set_both_hand_state(left_hand_state="open"))
                    for _ in range(45):
                        env.step()
                checkpoint("before-recovery")
                boundary("before_recovery_decision")
                offset = np.array([self.lateral_offset_m, 0, 0])
                candidate_pick = pick + offset
                candidate_lift = lift + offset
                self.record["candidate_targets_world_m"] = {"pick": candidate_pick.tolist(),
                                                             "lift": candidate_lift.tolist()}
                eligible = (np.all(np.isfinite([candidate_pick, candidate_lift]))
                            and np.linalg.norm(candidate_lift - candidate_pick) <= 0.32)
                if self.closed_hand:
                    before = np.median([x["patch_minus_tip_midpoint_m"] for x in self.record["before_disturbance"]],
                                       axis=0)
                    after = np.asarray([x["patch_minus_tip_midpoint_m"] for x in self.record["after_disturbance"]])
                    drift = np.linalg.norm(after - before, axis=1)
                    eligible = eligible and bool(np.all(drift > 0.04 * TCLC_018_W0_M))
                    self.record["slip_proxy_gate"] = {"passed": eligible, "minimum_drift_m": float(drift.min()),
                                                      "w0_m": TCLC_018_W0_M,
                                                      "contact_sensor_available": False}
                if eligible:
                    self.record["diagnostic_gate"] = "finite upstream targets; pick-to-lift distance <= 0.32 m"
                    if self.closed_hand:
                        attempt("regrasp-open", lambda: robot.set_both_hand_state(left_hand_state="open"))
                        for _ in range(45):
                            env.step()
                    if attempt("approach-regrasp-pick", lambda: original(candidate_pick, target_ori, *args, **kwargs)):
                        attempt("close", lambda: robot.set_both_hand_state(left_hand_state="close"))
                        for _ in range(12):
                            env.step()
                        attempt("lift", lambda: original(candidate_lift, target_ori, *args, **kwargs))
                else:
                    self.record["diagnostic_gate"] = "rejected"
                checkpoint("after-recovery")
                boundary("fixed_first_sleeve_transfer")
            result = original(target_pos, target_ori, *args, **kwargs)
            if move_count == 3:
                self.record["resume_sdk_result"] = bool(result)
                checkpoint("after-resume-transfer")
                if trace:
                    boundary("after_first_sleeve_transfer")
                    env.world.step = original_step
                    robot.set_both_hand_state = original_hand
                    for side, controller in controllers.items():
                        controller.apply_action = dispatch[side]
                    trace.save(self.record["injection"], scope="full_fold_first_sleeve_recovery_prefix")
                self.save()
            return result

        left.dense_step_action = move

    def finish(self, env):
        if env is None or self.record["judgment"] is None:
            self.save()
            return
        self.snapshot(env, "final")
        marker = os.environ.get("ROBOTICS_PROBE_MARKER")
        if marker:
            Path(marker).write_text(str(self.output / "full-fold-recovery.json"), encoding="utf-8")
        print("FOLD_RECOVERY_MEASURED", self.output, flush=True)
