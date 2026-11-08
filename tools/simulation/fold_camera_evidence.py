"""Capture Fold Tops RGB and check the simulated camera projection after the run."""
import json
import os
from pathlib import Path
import time
import uuid

import numpy as np
from scipy.ndimage import label


def measure_calibration(before, after, centers, projected, tolerance_px):
    rgb = after.astype(np.int16)
    changed = np.max(np.abs(rgb - before.astype(np.int16)), axis=2) > 30
    targets = []
    for index, (world_xyz, expected) in enumerate(zip(centers, projected)):
        other = np.max(np.delete(rgb, index, axis=2), axis=2)
        components, count = label(changed & (rgb[..., index] - other > 45))
        ys, xs = (np.array([]), np.array([]))
        if count:
            largest = 1 + np.argmax(np.bincount(components.ravel())[1:])
            ys, xs = np.where(components == largest)
        measured = np.array([xs.mean(), ys.mean()]) if xs.size else None
        targets.append({
            "world_xyz": world_xyz.tolist(), "projected_uv": expected.tolist(),
            "measured_uv": measured.tolist() if measured is not None else None,
            "error_px": float(np.linalg.norm(measured - expected)) if measured is not None else None,
            "color_pixel_count": int(xs.size),
        })
    return {"pixel_method": "centroid of largest connected changed color region per target",
            "targets": targets, "tolerance_px": tolerance_px,
            "passed": len(targets) == 3 and all(
                t["error_px"] is not None and t["error_px"] <= tolerance_px for t in targets)}


class FoldCameraEvidence:
    def __init__(self, root, base_env):
        from Env_Config.Utils_Project import Position_Judge

        self.output = root / ("fold-camera-" + str(uuid.uuid4()))
        self.output.mkdir(parents=True)
        self.record = {"garment": "TCLC_018", "frames": {}, "upstream_judge": None}
        self.start_ns = time.monotonic_ns()
        stop_record = base_env.stop_record
        judge = Position_Judge.judge_pcd

        def collect(env):
            stage = env.stage_index if env.record_flag else None
            result = stop_record(env)
            if stage is not None:
                self.capture(env, f"stage-{stage}")
            return result

        def collect_judgment(*args, **kwargs):
            result = judge(*args, **kwargs)
            self.record["upstream_judge"] = bool(result)
            self.save()
            return result

        base_env.stop_record = collect
        Position_Judge.judge_pcd = collect_judgment
        self.save()
        print("FOLD_CAMERA_EVIDENCE", self.output, flush=True)

    def save(self):
        self.record["wall_elapsed_s"] = (time.monotonic_ns() - self.start_ns) / 1e9
        (self.output / "evidence.json").write_text(json.dumps(self.record, indent=2, allow_nan=False),
                                                   encoding="utf-8")

    def capture(self, env, label):
        import imageio.v2 as imageio

        camera = env.env_camera.camera
        begin_ns = time.monotonic_ns()
        frame = camera.get_current_frame()
        rgba = np.asarray(frame.get("rgba"))
        width, height = camera.get_resolution()
        entry = {"sim_step": env.world.current_time_step_index, "sim_time_s": env.world.current_time,
                 "capture_wall_monotonic_ns": begin_ns, "image": None, "rgb_status": "missing"}
        self.record["frames"][label] = entry
        if rgba.shape != (height, width, 4) or rgba.dtype != np.uint8:
            self.save()
            return None
        rgb = rgba[..., :3].copy()
        image = label + ".png"
        imageio.imwrite(self.output / image, rgb)
        entry.update(image=image, rgb_status="nonuniform" if rgb.min() < rgb.max() else "uniform",
                     rgb_min=int(rgb.min()), rgb_max=int(rgb.max()), rgb_std=float(rgb.std()),
                     shape=list(rgb.shape), rendering_frame=int(frame["rendering_frame"]),
                     rendering_time_s=float(frame["rendering_time"]))
        self.save()
        return rgb

    def finish(self, env):
        from isaacsim.core.api.objects import VisualSphere

        if env is None or self.record["upstream_judge"] is None:
            return
        before = self.capture(env, "final")
        if before is None:
            return
        camera = env.env_camera.camera
        intrinsics = np.asarray(camera.get_intrinsics_matrix())
        world_to_camera = np.asarray(camera.get_view_matrix_ros())
        # Place three known-size color targets in front of the camera, after the
        # upstream judge and trajectory export have already finished.
        camera_centers = np.array([[-0.35, -0.25, 2.0, 1], [0.0, 0.27, 2.4, 1],
                                   [0.42, -0.25, 2.8, 1]])
        centers = (np.linalg.inv(world_to_camera) @ camera_centers.T).T[:, :3]
        projected = np.asarray(camera.get_image_coords_from_world_points(centers))
        for index, (center, color) in enumerate(zip(centers, np.eye(3))):
            VisualSphere(prim_path=f"/World/FoldCameraCalibration/Target{index}", position=center,
                         radius=0.035, color=color)
        for _ in range(15):
            env.step()
        after = self.capture(env, "calibration")
        if after is None:
            return
        calibration = measure_calibration(before, after, centers, projected, 3.0)
        self.record["calibration"] = {"camera_prim": camera.prim_path, "intrinsics_px": intrinsics.tolist(),
                                       "world_to_ros_camera": world_to_camera.tolist(),
                                       "sphere_radius_stage_units": 0.035,
                                       **calibration}
        self.save()
        required_frames = ("stage-1", "stage-2", "stage-3", "final", "calibration")
        if any(self.record["frames"].get(name, {}).get("image") is None for name in required_frames):
            return
        marker = os.environ.get("ROBOTICS_PROBE_MARKER")
        if marker:
            Path(marker).write_text(str(self.output / "evidence.json"), encoding="utf-8")
        print("FOLD_CAMERA_MEASURED", self.output, flush=True)
