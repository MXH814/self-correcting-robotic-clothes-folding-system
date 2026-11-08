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
    camera = Recording_Camera(camera_position=np.array([0, 4.0, 6.0]),
                              camera_orientation=np.array([0, 60, -90.0]))
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

    env.reset()
    camera.initialize(depth_enable=False)
    baseline = None
    patch_ids = None
    midstate_mode = os.environ.get("ROBOTICS_MIDSTATE_PROBE") == "1"
    midstate_references = []
    if midstate_mode:
        result["scope"] = "first_sleeve_failed_prefix_replay_and_restore_probe"
        result["resume_phase"] = "fixed_transfer"
        result["restored_contact_state"] = None
        result["restored_simulator_rng_state"] = None

    def measured_state():
        first = vertices()
        first_time = env.world.current_time
        tick(1)
        second = vertices()
        return {"vertices_m": second,
                "vertex_velocity_m_s": (second - first) / (env.world.current_time - first_time),
                "joint_position_rad": np.concatenate([a.get_joint_positions() for a in (arm, robot.dexright)]),
                "joint_velocity_rad_s": np.concatenate([a.get_joint_velocities() for a in (arm, robot.dexright)])}

    def state_errors(reference, replay):
        errors = {}
        for key in reference:
            delta = replay[key] - reference[key]
            if delta.ndim == 2:
                delta = np.linalg.norm(delta, axis=1)
            errors[key] = {"max_abs": float(np.abs(delta).max()),
                           "rms": float(np.sqrt(np.mean(delta ** 2)))}
        return errors

    start = time.perf_counter()
    conditions = (("unexpected_release",) * 3 if midstate_mode else
                  ("normal", "grasp_offset", "unexpected_release", "offset_regrasp", "release_regrasp"))
    for case_index, condition in enumerate(conditions):
        env.reset()
        garment.set_pose(pos=origin, ori=zeros)
        robot.set_both_hand_state("open", "open")
        tick(100)
        root = vertices()
        if baseline is None:
            baseline = root
            patch_ids = np.argsort(np.linalg.norm(root[:, :2] - pick[:2], axis=1))[:12]
            result["tracked_mesh_vertex_ids"] = patch_ids.tolist()
        err = np.linalg.norm(root - baseline, axis=1)
        trial = {"condition": condition, "case_index": case_index, "root_mesh_rms_m": float(np.sqrt(np.mean(err ** 2))),
                 "root_mesh_max_m": float(err.max()), "samples": [], "continuous_samples": [],
                 "motions": [], "hand_commands": [], "images": {},
                 "dr02_label": None, "terminal_task_result": None}
        result["trials"].append(trial)
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
            if rgb is not None and rgb.shape == (480, 640, 3):
                prefix = f"replay-{case_index}" if midstate_mode else condition
                name = f"{prefix}-{label}.png"
                imageio.imwrite(output / name, rgb)
                trial["images"][label] = name
            save()

        def timestamp():
            return {"sim_time_s": env.world.current_time, "wall_monotonic_ns": time.monotonic_ns()}

        def hand(label, state):
            nonlocal current_phase
            current_phase = label
            begin = timestamp()
            robot.set_both_hand_state(left_hand_state=state)
            trial["hand_commands"].append({"phase": label, "state": state, "begin": begin, "end": timestamp()})

        def move(label, target):
            nonlocal current_phase
            current_phase = label
            begin = timestamp()
            success = arm.dense_step_action(target, orientation)
            trial["motions"].append({"phase": label, "target_m": target.tolist(), "ik_reported": bool(success),
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
            return result

        try:
            measure(current_phase, 0, "continuous_samples")
            env.world.step = sample_step
            shifted = condition in ("grasp_offset", "offset_regrasp")
            opened_early = condition in ("unexpected_release", "release_regrasp")
            applied_pick = pick + offset if shifted else pick.copy()
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
            window("hold")
            if midstate_mode:
                midstate = measured_state()
                midstate_references.append(midstate)
                trial["midstate_sim_time_s"] = env.world.current_time
                trial["midstate_error_vs_first"] = state_errors(midstate_references[0], midstate)
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
        save()
        print("GARMENT_FAULT_CASE_RECORDED", condition, flush=True)
    if midstate_mode:
        if len(midstate_references) != len(conditions):
            raise RuntimeError("A replay did not reach the recorded failure point")
        reference = midstate_references[0]
        direct = {"particle_state_applied": False, "joint_state_applied": False}
        result["direct_restore"] = direct
        current = vertices()
        try:
            cloth = garment.particle_controller
            cloth.initialize()
            solver = np.asarray(cloth.get_world_positions())
            direct["solver_particle_shape"] = list(solver.shape)
            if solver.shape != (1, *current.shape):
                raise RuntimeError("Particle view shape differs from the measured mesh")
            order_error = float(np.linalg.norm(solver[0] - current, axis=1).max())
            direct["solver_to_mesh_max_m"] = order_error
            if not np.isfinite(solver).all() or order_error > 0.001:
                raise RuntimeError("Particle-to-mesh correspondence could not be verified within 1 mm")
            cloth.set_world_positions(reference["vertices_m"][None].astype(np.float32))
            cloth.set_velocities(reference["vertex_velocity_m_s"][None].astype(np.float32))
            direct["particle_state_applied"] = True
            direct["particle_position_error_after_apply_m"] = float(
                np.linalg.norm(np.asarray(cloth.get_world_positions())[0] - reference["vertices_m"], axis=1).max())
        except (RuntimeError, AttributeError, TypeError, ValueError) as error:
            direct["particle_restore_error"] = str(error)
        for index, a in enumerate((arm, robot.dexright)):
            channels = slice(30 * index, 30 * (index + 1))
            a.set_joint_positions(reference["joint_position_rad"][channels])
            a.set_joint_velocities(reference["joint_velocity_rad_s"][channels])
        direct["joint_state_applied"] = True
        direct["joint_error_immediate"] = state_errors(
            {key: reference[key] for key in ("joint_position_rad", "joint_velocity_rad_s")},
            {"joint_position_rad": np.concatenate([a.get_joint_positions() for a in (arm, robot.dexright)]),
             "joint_velocity_rad_s": np.concatenate([a.get_joint_velocities() for a in (arm, robot.dexright)])})
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
