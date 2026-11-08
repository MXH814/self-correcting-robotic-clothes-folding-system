"""Collect first-sleeve disturbance evidence with DexGarmentLab's actual cloth and arm."""
import json
import os
from pathlib import Path
import sys
import time
import traceback
import uuid

from isaacsim import SimulationApp


class CaseAbort(RuntimeError):
    """Stop a case before dispatching further motion after invalid evidence."""


def run(output):
    import imageio.v2 as imageio
    import numpy as np
    from pxr import Usd, UsdGeom
    from Env_Config.Camera.Recording_Camera import Recording_Camera
    from Env_Config.Garment.Particle_Garment import Particle_Garment
    from Env_Config.Robot.BimanualDex_Ur10e import Bimanual_Ur10e
    from Env_Config.Room.Real_Ground import Real_Ground
    from Env_StandAlone.BaseEnv import BaseEnv

    env = BaseEnv()
    env.physics.set_gpu_max_rigid_contact_count(262144)
    env.physics.set_gpu_max_rigid_patch_count(262144)
    Real_Ground(env.scene)
    origin = np.array([0.0, 0.8, 0.2])
    zeros = np.zeros(3)
    asset = "Assets/Garment/Tops/Collar_Lsleeve_FrontClose/TCLC_018/TCLC_018_obj.usd"
    garment = Particle_Garment(env.world, pos=origin, ori=zeros, usd_path=str(Path(asset).resolve()),
                               contact_offset=0.012, rest_offset=0.010, particle_contact_offset=0.012,
                               fluid_rest_offset=0.010, solid_rest_offset=0.010)
    robot = Bimanual_Ur10e(env.world, np.array([-0.8, 0, 0.5]), zeros, np.array([0.8, 0, 0.5]), zeros)
    arm = robot.dexleft
    trace_condition = os.environ.get("ROBOTICS_GARMENT_TRACE_CASE")
    cases = ("normal", "grasp_offset", "unexpected_release", "offset_regrasp", "release_regrasp")
    if trace_condition and trace_condition not in (*cases, "contact_offset_candidate", "closed_hand_slip_candidate"):
        raise ValueError(f"Unknown garment trace case: {trace_condition}")
    resolution = (240, 180) if trace_condition else (640, 480)
    camera = Recording_Camera(camera_position=np.array([0, 4.0, 6.0]),
                              camera_orientation=np.array([0, 60, -90.0]), resolution=resolution,
                              frequency=30 if trace_condition else 20)
    pick = np.array([-0.4600427, 0.6103945, 0.02])
    transfer = np.array([0.160156, 1.0065818, 0.30])
    orientation = np.array([0.579, -0.579, -0.406, 0.406])
    offset = np.array([-0.13, 0, 0])
    mesh = garment.garment_mesh
    tips = [env.world.stage.GetPrimAtPath(f"/World/DexLeft/{name}") for name in ("fftip", "thtip")]
    if not all(tip.IsValid() for tip in tips):
        raise RuntimeError("The configured left hand tip prims were not found")
    result = {"asset": asset, "scope": "first_sleeve_only", "pick_world_m": pick.tolist(),
              "transfer_world_m": transfer.tolist(), "left_orientation_wxyz": orientation.tolist(),
              "offset_world_m": offset.tolist(), "torso_reference_width_w0_m": None,
              "hand_proxy_source": [str(tip.GetPath()) for tip in tips],
              "contact_sensor": None, "trials": []}

    def save():
        (output / "fault-evidence.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")

    def vertices():
        points = np.asarray(mesh._get_points_pose())
        transform = UsdGeom.Xformable(mesh.prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        return (np.column_stack((points, np.ones(len(points)))) @ np.asarray(transform))[:, :3]

    def center():
        positions = [UsdGeom.Xformable(tip).ComputeLocalToWorldTransform(
            Usd.TimeCode.Default()).ExtractTranslation() for tip in tips]
        return np.asarray(positions).mean(axis=0)

    def tick(count):
        for _ in range(count):
            env.step()

    if trace_condition:
        np.savez_compressed(output / "reference-vertices.npz", vertices_m=vertices())
    env.reset()
    camera.initialize(depth_enable=False)
    baseline = None
    patch_ids = None
    start = time.perf_counter()
    for condition in (trace_condition,) if trace_condition else cases:
        env.reset()
        garment.set_pose(pos=origin, ori=zeros)
        robot.set_both_hand_state("open", "open")
        tick(100)
        root = vertices()
        if trace_condition:
            np.savez_compressed(output / "settled-vertices.npz", vertices_m=root)
        if baseline is None:
            baseline = root
            patch_ids = np.argsort(np.linalg.norm(root[:, :2] - pick[:2], axis=1))[:12]
            result["tracked_mesh_vertex_ids"] = patch_ids.tolist()
        err = np.linalg.norm(root - baseline, axis=1)
        trial = {"trial_id": str(uuid.uuid4()), "condition": condition,
                 "root_mesh_rms_m": None if trace_condition else float(np.sqrt(np.mean(err ** 2))),
                 "root_mesh_max_m": None if trace_condition else float(err.max()),
                 "samples": [], "continuous_samples": [],
                 "motions": [], "hand_commands": [], "images": {},
                 "dr02_label": None, "terminal_task_result": None}
        result["trials"].append(trial)
        trace = None
        original_apply = {}
        if trace_condition:
            from garment_observation_trace import GarmentObservationTrace
            arms = {"left": arm, "right": robot.dexright}
            trace = GarmentObservationTrace(output, env.world, camera.camera, arms, trial["trial_id"])
            for side, robot_arm in arms.items():
                controller = robot_arm.get_articulation_controller()
                original_apply[side] = (controller, controller.apply_action)
        patch_z0 = float(root[patch_ids, 2].mean())

        def measure(label, index, stream="samples"):
            tracked = vertices()[patch_ids]
            palm = center()
            if not np.isfinite(tracked).all() or np.max(np.abs(tracked)) > 3.0:
                raise CaseAbort(f"tracked cloth outside the diagnostic bounds in {label}")
            relative = tracked.mean(axis=0) - palm
            trial[stream].append({"phase": label, "index": index,
                                     "sim_time_s": env.world.current_time,
                                     "wall_monotonic_ns": time.monotonic_ns(),
                                     "patch_xyz_m": tracked.mean(axis=0).tolist(), "hand_proxy_xyz_m": palm.tolist(),
                                     "patch_minus_hand_m": relative.tolist(),
                                     "patch_height_gain_m": float(tracked[:, 2].mean() - patch_z0)})

        def window(label):
            for index in range(8):
                measure(label, index)
                if index < 7:
                    tick(3)
            rgb = camera.get_rgb_graph()
            if rgb is not None and rgb.shape == (resolution[1], resolution[0], 3):
                name = f"{condition}-{label}.png"
                imageio.imwrite(output / name, rgb)
                trial["images"][label] = name
            save()

        def timestamp():
            return {"sim_time_s": env.world.current_time, "wall_monotonic_ns": time.monotonic_ns()}

        def hand(label, state):
            nonlocal current_phase
            current_phase = label
            if trace:
                trace.boundary(label)
            begin = timestamp()
            robot.set_both_hand_state(left_hand_state=state)
            trial["hand_commands"].append({"phase": label, "state": state, "begin": begin, "end": timestamp()})

        def move(label, target, step_m=0.01):
            nonlocal current_phase
            current_phase = label
            if trace:
                trace.boundary(label)
            begin = timestamp()
            success = arm.dense_step_action(target, orientation, dense_sample_scale=step_m)
            trial["motions"].append({"phase": label, "target_m": target.tolist(), "ik_reported": bool(success),
                                     "dense_sample_scale_m": step_m,
                                     "begin": begin, "end": timestamp()})
            if not success:
                raise CaseAbort(f"upstream IK reported failure in {label}")
            tick(12)

        current_phase = "before_approach"
        count = 0
        original_step = env.world.step

        def sample_step(*args, **kwargs):
            nonlocal count
            result = original_step(*args, **kwargs)
            count += 1
            if count % 3 == 0:
                measure(current_phase, count, "continuous_samples")
            if trace:
                trace.observe(current_phase)
            return result

        try:
            if trace:
                trace.boundary(current_phase)
                for side, (controller, apply) in original_apply.items():
                    controller.apply_action = trace.wrap_apply(side, apply, lambda: current_phase)
            measure(current_phase, 0, "continuous_samples")
            env.world.step = sample_step
            shifted = condition in ("grasp_offset", "offset_regrasp")
            opened_early = condition in ("unexpected_release", "release_regrasp")
            applied_pick = pick + offset if shifted else pick.copy()
            if condition == "contact_offset_candidate":
                applied_pick += np.array([0.046, 0.025, 0.0])
                trial["injection"] = {"kind": "shifted_approach", "offset_m": (applied_pick - pick).tolist()}
            move("approach", applied_pick)
            hand("expected_hold_begins", "close")
            tick(12)
            window("closed")
            lift = applied_pick.copy()
            lift[2] = 0.30
            move("lift", lift)
            window("lifted")
            if opened_early:
                # Diagnostic actuation during the hold phase, distinct from the
                # controller's planned release after the transfer.
                trial["injection"] = {"kind": "early_open_command", "sim_time_s": env.world.current_time}
                hand("injected_open_during_hold", "open")
            elif shifted:
                trial["injection"] = {"kind": "shifted_approach", "offset_m": offset.tolist()}
            elif condition == "closed_hand_slip_candidate":
                material = garment.particle_material
                original_friction = float(material.get_friction())
                trial["injection"] = {"kind": "reduced_friction_and_coarser_motion_during_closed_hold",
                                      "sim_time_s": env.world.current_time,
                                      "original_friction": original_friction, "friction": 0.0}
                try:
                    material.set_friction(0.0)
                    move("disturbance_closed_hand", lift + np.array([0.20, 0.10, 0.02]), step_m=0.04)
                    window("disturbance_closed_hand")
                finally:
                    material.set_friction(original_friction)
            window("hold")
            if condition.endswith("_regrasp"):
                trial["candidate"] = "scripted_regrasp_at_original_pick"
                hand("experimental_regrasp_release", "open")
                move("regrasp_retreat", lift + np.array([0, -0.15, 0.05]))
                tick(45)
                move("regrasp_approach", pick)
                hand("experimental_regrasp_close", "close")
                tick(12)
                window("regrasp_closed")
                move("regrasp_lift", np.array([pick[0], pick[1], 0.30]))
                window("regrasp_lifted")
            move("fixed_transfer", transfer)
            window("transferred")
            hand("planned_release", "open")
            tick(24)
            window("planned_release")
            trial["status"] = "completed"
        except CaseAbort as error:
            trial.update(status="aborted", abort_reason=str(error))
        finally:
            env.world.step = original_step
            for controller, apply in original_apply.values():
                controller.apply_action = apply
        if trace:
            trace.boundary("trial_end")
            trace.save(condition)
        save()
        print("GARMENT_FAULT_CASE_RECORDED", condition, flush=True)
    result["wall_elapsed_s"] = time.perf_counter() - start
    save()


if __name__ == "__main__":
    root = Path(os.environ["ROBOTICS_PROJECT_ROOT"]).resolve()
    os.chdir(root)
    sys.path.insert(0, str(root))
    output = Path(os.environ["ROBOTICS_OUTPUT_ROOT"]) / ("garment-fault-" + str(uuid.uuid4()))
    output.mkdir(parents=True)
    app = SimulationApp({"headless": True, "width": 640, "height": 480, "multi_gpu": False,
                         "extra_args": ["--/plugins/carb.tasking.plugin/threadCount=4",
                                        "--/plugins/omni.tbb.globalcontrol/maxThreadCount=4",
                                        "--/persistent/physics/numThreads=4"]})
    try:
        run(output)
        marker = os.environ.get("ROBOTICS_PROBE_MARKER")
        if marker:
            Path(marker).write_text(str(output / "fault-evidence.json"), encoding="utf-8")
        print("GARMENT_FAULT_PROBE_COMPLETE", output, flush=True)
    except Exception:
        (output / "capture-error.txt").write_text(traceback.format_exc(), encoding="utf-8")
        raise
    finally:
        app.close()
