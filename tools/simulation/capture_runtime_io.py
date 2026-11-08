"""Collect a small *component-level* Isaac Sim joint I/O sample.

This is not the project coordinator/adapter, a folding run, or a stop test.
Run through run_local.ps1 so that Isaac's Python and local dependencies are used.
"""
import json
import os
from pathlib import Path
import sys
import time
import traceback
import uuid
from datetime import datetime, timezone

root = Path(os.environ["ROBOTICS_PROJECT_ROOT"]).resolve()
output_root = Path(os.environ["ROBOTICS_OUTPUT_ROOT"]).resolve()
output_root.mkdir(parents=True, exist_ok=True)
os.chdir(root)
sys.path.insert(0, str(root))
run_id = str(uuid.uuid4())
out = output_root / ("runtime-io-" + run_id)
out.mkdir()

def checkpoint(name):
    with (out / "progress.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"stage": name, "wall_monotonic_ns": time.monotonic_ns()}) + "\n")
    print("CAPTURE_STAGE", name, flush=True)

checkpoint("starting_simulation_app")

from isaacsim import SimulationApp

app = SimulationApp({"headless": True, "width": 640, "height": 480, "extra_args": [
    "--/plugins/carb.tasking.plugin/threadCount=4",
    "--/plugins/omni.tbb.globalcontrol/maxThreadCount=4",
    "--/persistent/physics/numThreads=4",
]})
checkpoint("simulation_app_started")

try:
    import numpy as np
    import omni.physics.tensors
    import imageio.v2 as imageio
    from pxr import Gf, UsdGeom, UsdLux
    from isaacsim.core.api import World
    from isaacsim.core.utils.stage import get_current_stage
    from isaacsim.core.utils.types import ArticulationAction
    from Env_Config.Robot.BimanualDex_Ur10e import Bimanual_Ur10e
    from Env_Config.Camera.Recording_Camera import Recording_Camera

    checkpoint("imports_complete")

    world = World(stage_units_in_meters=1.0)
    robot = Bimanual_Ur10e(world, np.array([-0.8, 0, 0.5]), np.zeros(3),
                           np.array([0.8, 0, 0.5]), np.zeros(3))
    stage = get_current_stage()
    light = UsdLux.DomeLight.Define(stage, "/World/RuntimeProbeDomeLight")
    light.CreateIntensityAttr(1000.0)
    eye = [0.0, 3.6, 3.2]
    look_at_target = [0.0, 0.5, 0.6]
    resolution = (640, 480)
    camera = Recording_Camera(camera_position=np.array(eye), resolution=resolution)
    checkpoint("scene_created")
    world.reset()
    checkpoint("world_reset")
    camera.initialize(depth_enable=True)
    # Set the sensor prim directly so aiming works without an active viewport.
    view = Gf.Matrix4d().SetLookAt(Gf.Vec3d(*eye), Gf.Vec3d(*look_at_target), Gf.Vec3d(0, 0, 1))
    rotation = view.GetInverse().ExtractRotationQuat()
    camera.camera.set_world_pose(position=np.array(eye),
                                 orientation=np.array([rotation.GetReal(), *rotation.GetImaginary()]),
                                 camera_axes="usd")
    camera.camera.set_focal_length(2.4)
    camera.camera.set_horizontal_aperture(2.4)
    camera_position, camera_orientation = camera.camera.get_world_pose(camera_axes="usd")
    checkpoint("camera_initialized")
    for _ in range(30):
        world.step(render=True)
    checkpoint("initial_steps_complete")

    def clock():
        return {"wall_monotonic_ns": time.monotonic_ns(),
                "sim_time_s": float(world.current_time),
                "sim_step": int(world.current_time_step_index)}

    def profile(arm):
        props = arm.dof_properties
        names = arm.dof_names
        # SingleArticulation.dof_properties uses get_dof_types()[0] in this
        # Isaac version, which broadcasts one type; read each type directly.
        types = arm._articulation_view.get_dof_types()
        if len(names) != len(props) or len(names) != len(types):
            raise RuntimeError("runtime DOF names, types and properties differ in length")
        records = []
        for index, name in enumerate(names):
            p = props[index]
            actual_type = types[index]
            if actual_type == omni.physics.tensors.DofType.Rotation:
                kind, pos_unit, vel_unit = "rotation", "rad", "rad/s"
            elif actual_type == omni.physics.tensors.DofType.Translation:
                kind, pos_unit, vel_unit = "translation", "stage_unit", "stage_unit/s"
            else:
                kind, pos_unit, vel_unit = "unknown", None, None
            records.append({"index": index, "name": name, "type": kind,
                            "runtime_type_repr": str(actual_type),
                            "position_unit": pos_unit, "velocity_unit": vel_unit,
                            "has_limits": bool(p["hasLimits"]),
                            "lower": float(p["lower"]), "upper": float(p["upper"]),
                            "drive_mode_code": int(p["driveMode"]),
                            "stiffness": float(p["stiffness"]), "damping": float(p["damping"])})
        return records

    def observe():
        before = clock()
        left_pos = robot.dexleft.get_joint_positions().tolist()
        left_vel = robot.dexleft.get_joint_velocities().tolist()
        right_pos = robot.dexright.get_joint_positions().tolist()
        right_vel = robot.dexright.get_joint_velocities().tolist()
        after = clock()
        return {"capture_begin": before, "capture_end": after,
                "left_positions": left_pos, "left_velocities": left_vel,
                "right_positions": right_pos, "right_velocities": right_vel}

    sample = {"schema": "component-runtime-io-v1", "run_id": run_id,
              "created_utc": datetime.now(timezone.utc).isoformat(),
              "scope": "headless robot and simulated camera component probe; no garment, folding, project adapter or stop test",
              "clock_scope": "time.monotonic_ns on this process/host; not synchronized to any external coordinator",
              "stage_meters_per_unit": float(UsdGeom.GetStageMetersPerUnit(stage)),
              "stage_up_axis": str(UsdGeom.GetStageUpAxis(stage)),
              "left_prim": "/World/DexLeft", "right_prim": "/World/DexRight",
              "left_dofs": profile(robot.dexleft), "right_dofs": profile(robot.dexright),
              "camera": {"prim_path": camera.camera_prim_path, "source": "Isaac Sim simulated camera RGB",
                         "configured_position_stage_units": eye,
                         "look_at_target_stage_units": look_at_target,
                         "world_position_stage_units": camera_position.tolist(),
                         "world_orientation_usd_wxyz": camera_orientation.tolist(),
                         "orientation_convention": "USD camera axes (-Z forward, +Y up); quaternion wxyz",
                         "focal_length": camera.camera.get_focal_length(),
                         "horizontal_aperture": camera.camera.get_horizontal_aperture(),
                         "dome_light_intensity": float(light.GetIntensityAttr().Get()),
                         "configured_resolution": list(resolution), "configured_frequency_hz": camera.frequency,
                         "depth_enabled": True, "frame_timestamp": None},
              "adapter_ack": None, "stop_request": None, "stop_feedback": None,
              "observations": []}
    checkpoint("profile_read")
    before = observe()
    checkpoint("before_observation_read")
    sample["observations"].append(before)
    index = int(robot.dexleft.arm_dof_indices[0])
    prop = sample["left_dofs"][index]
    if prop["type"] != "rotation":
        raise RuntimeError("selected joint is not reported as rotational")
    current = float(before["left_positions"][index])
    target = current + 0.03
    if prop["has_limits"] and not prop["lower"] <= target <= prop["upper"]:
        raise RuntimeError("probe target outside reported joint limits")
    command = {"command_id": str(uuid.uuid4()), "kind": "absolute_joint_position_target",
               "joint_name": prop["name"], "joint_index": index, "unit": "rad",
               "current_position_before": current, "target": target,
               "target_construction_offset_rad": 0.03,
               "issued": clock(), "api": "DexLeft.apply_action(ArticulationAction)",
               "adapter_ack": None, "api_returned": None}
    sample["command"] = command
    robot.dexleft.apply_action(ArticulationAction(joint_positions=np.array([target]),
                                                  joint_indices=np.array([index])))
    checkpoint("api_returned")
    command["api_returned"] = clock()
    for step in range(60):
        world.step(render=True)
        if step in (0, 9, 29, 59):
            sample["observations"].append(observe())
    checkpoint("feedback_steps_complete")
    image_begin = clock()
    frame = camera.camera.get_current_frame()
    rgba = np.asarray(frame.get("rgba"))
    image_end = clock()
    sample["camera"].update({"image": None, "rgb_status": "missing",
                             "read_begin": image_begin, "read_end": image_end})
    if rgba.shape == (resolution[1], resolution[0], 4) and rgba.dtype == np.uint8:
        rgb = rgba[..., :3]
        rgb_min, rgb_max = int(rgb.min()), int(rgb.max())
        status = "all_black" if rgb_max == 0 else "uniform" if rgb_min == rgb_max else "nonuniform"
        imageio.imwrite(out / "camera-rgb.png", rgb)
        sample["camera"].update({"image": "camera-rgb.png", "shape": list(rgb.shape),
                                 "dtype": str(rgb.dtype), "rgb_status": status,
                                 "rgb_min": rgb_min, "rgb_max": rgb_max, "rgb_std": float(rgb.std()),
                                 "rendering_frame": int(frame["rendering_frame"]),
                                 "rendering_time_s": float(frame["rendering_time"])})
    (out / "sample.json").write_text(json.dumps(sample, indent=2, allow_nan=False), encoding="utf-8")
    checkpoint("sample_written")
    if os.environ.get("ROBOTICS_PROBE_MARKER"):
        Path(os.environ["ROBOTICS_PROBE_MARKER"]).write_text(str(out), encoding="utf-8")
    print("COMPONENT_SAMPLE_WRITTEN", out, flush=True)
except BaseException:
    failure = traceback.format_exc()
    (out / "capture-error.txt").write_text(failure, encoding="utf-8")
    print("CAPTURE_ERROR\n" + failure, flush=True)
    raise
finally:
    app.close()
