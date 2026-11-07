"""Small local integration check using DexGarmentLab's actual cloth and robot classes."""
import argparse
import json
import os
from pathlib import Path
import sys

parser = argparse.ArgumentParser()
parser.add_argument("--headless", action="store_true")
parser.add_argument("--stage", choices=["engine", "garment"], default="garment")
parser.add_argument("--keep-open", action="store_true")
args = parser.parse_args()
ROOT = Path(os.environ["ROBOTICS_PROJECT_ROOT"]).resolve()
OUTPUT = Path(os.environ["ROBOTICS_OUTPUT_ROOT"]).resolve()
OUTPUT.mkdir(parents=True, exist_ok=True)
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from isaacsim import SimulationApp
app = SimulationApp({"headless": args.headless, "width": 960, "height": 720, "extra_args": [
    "--/plugins/carb.tasking.plugin/threadCount=4",
    "--/plugins/omni.tbb.globalcontrol/maxThreadCount=4",
    "--/persistent/physics/numThreads=4",
]})

try:
    import numpy as np
    from isaacsim.core.api import World
    from isaacsim.core.api.objects import FixedCuboid, DynamicCuboid
    from isaacsim.core.utils.viewports import set_camera_view

    if args.stage == "engine":
        world = World()
        world.scene.add(FixedCuboid(prim_path="/World/Table", position=np.array([0, 0, -0.05]), scale=np.array([3, 3, 0.1]), size=1))
        cube = world.scene.add(DynamicCuboid(prim_path="/World/Cube", position=np.array([0, 0, 1.0]), size=0.1))
        world.reset()
        for _ in range(120):
            world.step(render=True)
        position, _ = cube.get_world_pose()
        assert np.isfinite(position).all() and 0.0 < float(position[2]) < 0.15, position
        result = {"status": "passed", "stage": "engine", "cube_final_position": position.tolist()}
    else:
        from Env_StandAlone.BaseEnv import BaseEnv
        from Env_Config.Garment.Particle_Garment import Particle_Garment
        from Env_Config.Robot.BimanualDex_Ur10e import Bimanual_Ur10e
        from Env_Config.Camera.Recording_Camera import Recording_Camera
        from isaacsim.core.utils.types import ArticulationAction
        import imageio.v2 as imageio

        env = BaseEnv()
        # This budget is specific to the small hardware smoke test, not a change to upstream experiment defaults.
        env.physics.set_gpu_max_rigid_contact_count(262144)
        env.physics.set_gpu_max_rigid_patch_count(262144)
        env.scene.add(FixedCuboid(prim_path="/World/Table", position=np.array([0, 0.7, -0.05]), scale=np.array([3.2, 3.2, 0.1]), size=1, color=np.array([0.45, 0.48, 0.5])))
        garment = Particle_Garment(env.world, usd_path=str(ROOT / "Assets/Garment/Tops/Collar_Lsleeve_FrontClose/TCLC_018/TCLC_018_obj.usd"), pos=np.array([0, 0.8, 0.2]), ori=np.zeros(3), visual_material_usd=None)
        robot = Bimanual_Ur10e(env.world, np.array([-0.8, 0, 0.5]), np.zeros(3), np.array([0.8, 0, 0.5]), np.zeros(3))
        camera = Recording_Camera(camera_position=np.array([0, 4.0, 6.0]), camera_orientation=np.array([0, 60, -90.0]), resolution=(640, 480))
        env.reset()
        garment.set_pose(pos=np.array([0, 0.8, 0.2]), ori=np.zeros(3))
        print("GARMENT_RESET", env.world.is_playing(), flush=True)
        camera.initialize(depth_enable=True)
        camera.camera.set_focal_length(2.4)
        camera.camera.set_horizontal_aperture(2.4)
        set_camera_view(eye=np.array([0, 3.6, 3.2]), target=np.array([0, 0.5, 0.6]), camera_prim_path=camera.camera_prim_path)
        set_camera_view(eye=np.array([0, 3.6, 3.2]), target=np.array([0, 0.5, 0.6]), camera_prim_path="/OmniverseKit_Persp")
        initial_cloth = np.asarray(garment.garment_mesh._get_points_pose()).copy()
        for _ in range(100):
            env.step()
        print("GARMENT_SETTLED", env.world.is_playing(), flush=True)
        preview = camera.get_rgb_graph()
        if preview is not None and preview.size:
            imageio.imwrite(OUTPUT / "initial-scene.png", preview)
        robot.set_both_hand_state("open", "open")
        before_left = robot.dexleft.get_joint_positions().copy()
        before_right = robot.dexright.get_joint_positions().copy()
        robot.set_both_hand_state("close", "close")
        for _ in range(60):
            env.step()
        after_left = robot.dexleft.get_joint_positions().copy()
        after_right = robot.dexright.get_joint_positions().copy()
        left_delta = float(np.max(np.abs(after_left - before_left)))
        right_delta = float(np.max(np.abs(after_right - before_right)))
        assert np.isfinite(after_left).all() and np.isfinite(after_right).all()
        assert left_delta > 0.001 and right_delta > 0.001, (left_delta, right_delta)
        print("HANDS_MOVED", left_delta, right_delta, env.world.is_playing(), flush=True)
        left_arm_index = robot.dexleft.arm_dof_indices[0]
        right_arm_index = robot.dexright.arm_dof_indices[0]
        robot.dexleft.apply_action(ArticulationAction(joint_positions=np.array([after_left[left_arm_index] + 0.03]), joint_indices=np.array([left_arm_index])))
        robot.dexright.apply_action(ArticulationAction(joint_positions=np.array([after_right[right_arm_index] - 0.03]), joint_indices=np.array([right_arm_index])))
        for _ in range(60):
            env.step()
        print("ARMS_STEPPED", env.world.is_playing(), flush=True)
        left_arm_delta = float(abs(robot.dexleft.get_joint_positions()[left_arm_index] - after_left[left_arm_index]))
        right_arm_delta = float(abs(robot.dexright.get_joint_positions()[right_arm_index] - after_right[right_arm_index]))
        assert left_arm_delta > 0.001 and right_arm_delta > 0.001, (left_arm_delta, right_arm_delta)
        final_cloth = np.asarray(garment.garment_mesh._get_points_pose()).copy()
        assert np.isfinite(final_cloth).all()
        cloth_delta = float(np.max(np.abs(final_cloth - initial_cloth)))
        assert cloth_delta > 1e-6, "No garment particle motion detected"
        rgb = camera.get_rgb_graph()
        assert rgb is not None and rgb.shape[:2] == (480, 640), getattr(rgb, "shape", None)
        assert float(np.std(rgb)) > 1.0, "Camera returned a constant frame"
        imageio.imwrite(OUTPUT / "garment-camera.png", rgb)
        result = {"status": "passed", "stage": "garment", "garment": "TCLC_018", "camera_shape": list(rgb.shape), "left_joint_count": int(after_left.size), "right_joint_count": int(after_right.size), "left_joint_max_change": left_delta, "right_joint_max_change": right_delta, "left_arm_change": left_arm_delta, "right_arm_change": right_arm_delta, "cloth_particle_max_change": cloth_delta, "gpu_contact_budget": 262144, "scope": "cloth physics, bimanual arm and hand commands, RGB camera; does not verify folding success"}
    (OUTPUT / (args.stage + "-result.json")).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("LOCAL_SMOKE_TEST_PASSED", json.dumps(result), flush=True)
    if args.keep_open:
        while app.is_running():
            app.update()
except Exception:
    import traceback
    (OUTPUT / (args.stage + "-error.txt")).write_text(traceback.format_exc(), encoding="utf-8")
    raise
finally:
    app.close()
