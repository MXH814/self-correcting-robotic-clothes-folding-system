"""Collect a small *component-level* Isaac Sim joint I/O sample.

This is not the project coordinator/adapter, a folding run, or a stop test.
Run through run_local.ps1 so that Isaac's Python and local dependencies are used.
"""
import json
import os
from pathlib import Path
import sys
import time
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

from isaacsim import SimulationApp

app = SimulationApp({"headless": True, "width": 640, "height": 480, "extra_args": [
    "--/plugins/carb.tasking.plugin/threadCount=4",
    "--/plugins/omni.tbb.globalcontrol/maxThreadCount=4",
    "--/persistent/physics/numThreads=4",
]})

try:
    import numpy as np
    import imageio.v2 as imageio
    from pxr import UsdGeom
    from isaacsim.core.api import World
    from isaacsim.core.utils.stage import get_current_stage
    from isaacsim.core.utils.types import ArticulationAction
    from Env_Config.Robot.BimanualDex_Ur10e import Bimanual_Ur10e
    from Env_Config.Camera.Recording_Camera import Recording_Camera

    world = World(stage_units_in_meters=1.0)
    robot = Bimanual_Ur10e(world, np.array([-0.8, 0, 0.5]), np.zeros(3),
                           np.array([0.8, 0, 0.5]), np.zeros(3))
    camera = Recording_Camera(camera_position=np.array([0, 4.0, 6.0]),
                              camera_orientation=np.array([0, 60, -90.0]),
                              resolution=(640, 480))
    world.reset()
    camera.initialize(depth_enable=True)
    for _ in range(30):
        world.step(render=True)

    def clock():
        return {"wall_monotonic_ns": time.monotonic_ns(),
                "sim_time_s": float(world.current_time),
                "sim_step": int(world.current_time_step_index)}

    def profile(arm):
        props = arm.dof_properties
        names = arm.dof_names
        if len(names) != len(props):
            raise RuntimeError("runtime DOF names and properties differ in length")
        records = []
        for index, name in enumerate(names):
            p = props[index]
            dof_type = int(p["type"])
            records.append({"index": index, "name": name, "type_code": dof_type,
                            "position_unit": {1: "rad", 2: "stage_unit"}.get(dof_type),
                            "velocity_unit": {1: "rad/s", 2: "stage_unit/s"}.get(dof_type),
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

    stage = get_current_stage()
    sample = {"schema": "component-runtime-io-v1", "run_id": run_id,
              "created_utc": datetime.now(timezone.utc).isoformat(),
              "scope": "headless robot and simulated camera component probe; no garment, folding, project adapter or stop test",
              "clock_scope": "time.monotonic_ns on this process/host; not synchronized to any external coordinator",
              "stage_meters_per_unit": float(UsdGeom.GetStageMetersPerUnit(stage)),
              "stage_up_axis": str(UsdGeom.GetStageUpAxis(stage)),
              "left_prim": "/World/DexLeft", "right_prim": "/World/DexRight",
              "left_dofs": profile(robot.dexleft), "right_dofs": profile(robot.dexright),
              "camera": {"prim_path": camera.camera_prim_path, "source": "Isaac Sim simulated camera RGB",
                         "configured_position_stage_units": [0, 4.0, 6.0],
                         "configured_euler_degrees": [0, 60, -90.0],
                         "orientation_convention": "DexGarmentLab euler_angles_to_quat(degrees=True); calibration not verified",
                         "configured_resolution": [640, 480], "configured_frequency_hz": camera.frequency,
                         "depth_enabled": True, "frame_timestamp": None},
              "adapter_ack": None, "stop_request": None, "stop_feedback": None,
              "observations": []}
    before = observe()
    sample["observations"].append(before)
    index = int(robot.dexleft.arm_dof_indices[0])
    prop = sample["left_dofs"][index]
    if prop["type_code"] != 1:
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
    command["api_returned"] = clock()
    for step in range(60):
        world.step(render=True)
        if step in (0, 9, 29, 59):
            sample["observations"].append(observe())
    image_begin = clock()
    rgb = camera.get_rgb_graph()
    image_end = clock()
    if rgb is not None and rgb.size:
        imageio.imwrite(out / "camera-rgb.png", rgb)
        sample["camera"].update({"image": "camera-rgb.png", "shape": list(rgb.shape),
                                 "dtype": str(rgb.dtype), "read_begin": image_begin,
                                 "read_end": image_end})
    else:
        sample["camera"]["image"] = None
    (out / "sample.json").write_text(json.dumps(sample, indent=2, allow_nan=False), encoding="utf-8")
    print("COMPONENT_SAMPLE_WRITTEN", out, flush=True)
finally:
    app.close()
