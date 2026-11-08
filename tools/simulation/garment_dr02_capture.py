"""Record near-hand RGB and raw cloth/rigid geometry for offline DR02 review."""
import json
import time

import numpy as np
from isaacsim.sensors.camera import Camera
from pxr import Gf, Usd, UsdGeom, UsdPhysics


class Dr02Capture:
    def __init__(self, output, world, tips):
        self.output = output
        self.world = world
        self.tips = tips
        self.resolution = (400, 300)
        self.camera = Camera("/World/dr02_near_hand", position=np.array([0.0, 0.0, 1.0]),
                             resolution=self.resolution, frequency=30)
        self.camera.set_focal_length(4.0)
        self.camera.set_clipping_range(0.02, 2.0)
        self.colliders = []
        robot = world.stage.GetPrimAtPath("/World/DexLeft")
        for prim in Usd.PrimRange(robot, Usd.TraverseInstanceProxies()):
            path = str(prim.GetPath()).lower()
            if (prim.HasAPI(UsdPhysics.CollisionAPI)
                    and any(link in path for link in ("ffdistal", "thdistal", "fftip", "thtip"))):
                self.colliders.append(prim)
        self.rows = []
        self.meshes = []
        self.tip_transforms = []
        self.collider_transforms = []
        self.camera_transforms = []
        self.frames = []
        self.frame_keys = {}

    def initialize(self):
        self.camera.initialize()
        self.camera.set_horizontal_aperture(3.6)

    def transform(self, prim):
        return np.asarray(UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default()))

    def aim(self):
        focus = np.asarray([self.transform(tip)[3, :3] for tip in self.tips]).mean(axis=0)
        eye = focus + np.array([0.11, -0.17, 0.14])
        view = Gf.Matrix4d().SetLookAt(Gf.Vec3d(*eye), Gf.Vec3d(*focus), Gf.Vec3d(0, 0, 1))
        quat = view.GetInverse().ExtractRotationQuat()
        self.camera.set_world_pose(position=eye,
                                   orientation=np.array([quat.GetReal(), *quat.GetImaginary()]),
                                   camera_axes="usd")

    def observe(self, phase, vertices, *, stream="window"):
        begin = time.monotonic_ns()
        frame = self.camera.get_current_frame()
        rgba = np.asarray(frame.get("rgba"))
        frame_index = None
        render_time = None
        if rgba.shape == (self.resolution[1], self.resolution[0], 4) and rgba.dtype == np.uint8:
            key = (int(frame["rendering_frame"]), float(frame["rendering_time"]))
            render_time = key[1]
            if key not in self.frame_keys:
                self.frame_keys[key] = len(self.frames)
                self.frames.append(rgba[:, :, :3].copy())
            frame_index = self.frame_keys[key]
        self.rows.append({"phase": phase, "stream": stream, "sim_time_s": float(self.world.current_time),
                          "sim_step": int(self.world.current_time_step_index), "frame_index": frame_index,
                          "rendering_time_s": render_time, "read_begin_monotonic_ns": begin,
                          "read_end_monotonic_ns": time.monotonic_ns()})
        self.meshes.append(vertices.astype(np.float32))
        self.tip_transforms.append([self.transform(tip) for tip in self.tips])
        self.collider_transforms.append([self.transform(prim) for prim in self.colliders])
        self.camera_transforms.append(self.transform(self.camera.prim))

    def save(self, trial_id, condition, patch_ids):
        arrays = {"cloth_world_m": np.stack(self.meshes), "tip_local_to_world": np.asarray(self.tip_transforms),
                  "collider_local_to_world": np.asarray(self.collider_transforms),
                  "camera_usd_to_world_at_sample": np.asarray(self.camera_transforms),
                  "rgb": np.stack(self.frames)}
        colliders = []
        for index, prim in enumerate(self.colliders):
            entry = {"path": str(prim.GetPath()), "type": prim.GetTypeName()}
            if prim.IsA(UsdGeom.Mesh):
                mesh = UsdGeom.Mesh(prim)
                for name, value in (("points", mesh.GetPointsAttr().Get()),
                                    ("face_vertex_indices", mesh.GetFaceVertexIndicesAttr().Get()),
                                    ("face_vertex_counts", mesh.GetFaceVertexCountsAttr().Get())):
                    key = f"collider_{index}_{name}"
                    arrays[key] = np.asarray(value)
                    entry[name] = key
            else:
                for name in ("radius", "height", "axis", "size"):
                    attr = prim.GetAttribute(name)
                    if attr:
                        entry[name] = attr.Get()
            colliders.append(entry)
        np.savez_compressed(self.output / "dr02-samples.npz", **arrays)
        (self.output / "dr02-samples.json").write_text(json.dumps(
            {"trial_id": trial_id, "condition": condition, "phase_samples": self.rows,
             "tip_prim_paths": [str(tip.GetPath()) for tip in self.tips],
             "colliders": colliders, "expected_patch_ids": patch_ids.tolist(),
             "camera_intrinsics_px": self.camera.get_intrinsics_matrix().tolist(),
             "pose_convention": "USD row-vector local-to-world matrices, world position in meters",
             "native_particle_contact_report": None, "dr02_label": None},
            indent=2, allow_nan=False), encoding="utf-8")
