"""Record causally ordered camera frames and actual articulation dispatches."""
import hashlib
import json
import time
import uuid

import numpy as np


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


class GarmentObservationTrace:
    def __init__(self, output, world, camera, arms, trial_id):
        self.output = output
        self.world = world
        self.camera = camera
        self.arms = arms
        self.trial_id = trial_id
        self.names = {side: list(arm.dof_names) for side, arm in arms.items()}
        self.frames = []
        self.frame_keys = {}
        self.observations = []
        self.actions = []
        self.pending_feedback = []
        self.boundaries = []

    def clock(self):
        return {"sim_time_s": float(self.world.current_time),
                "sim_step": int(self.world.current_time_step_index),
                "wall_monotonic_ns": time.monotonic_ns()}

    def observe(self, phase, *, force=False):
        begin = self.clock()
        frame = self.camera.get_current_frame()
        rgba = np.asarray(frame.get("rgba"))
        if rgba.ndim != 3 or rgba.shape[2] != 4 or rgba.dtype != np.uint8:
            if force:
                raise RuntimeError("Required action observation has no RGB")
            return None
        key = (int(frame["rendering_frame"]), float(frame["rendering_time"]))
        if key[1] > begin["sim_time_s"] + 1e-7:
            raise RuntimeError("Camera render time is later than observation read")
        if key in self.frame_keys and not force:
            return None
        if key not in self.frame_keys:
            self.frame_keys[key] = len(self.frames)
            self.frames.append(rgba[:, :, :3].copy())
        camera_end = self.clock()
        joint_state = {
            side: {"position_rad": arm.get_joint_positions().tolist(),
                   "velocity_rad_s": arm.get_joint_velocities().tolist()}
            for side, arm in self.arms.items()
        }
        obs = {"observation_id": str(uuid.uuid4()), "phase": phase,
               "frame_index": self.frame_keys[key], "rendering_frame": key[0],
               "rendering_time_s": key[1], "camera_read_begin": begin, "camera_read_end": camera_end,
               "joint_read_end": self.clock(), "joint_state": joint_state}
        self.observations.append(obs)
        still_pending = []
        for action in self.pending_feedback:
            if action["issue"]["sim_step"] < begin["sim_step"]:
                action["feedback_observation_id"] = obs["observation_id"]
            else:
                still_pending.append(action)
        self.pending_feedback = still_pending
        return obs

    def boundary(self, phase):
        obs = self.observe(phase, force=True)
        self.boundaries.append({"phase": phase, "observation_id": obs["observation_id"]})

    def wrap_apply(self, side, original, get_phase):
        def apply(control_actions):
            obs = self.observations[-1]
            fields = {}
            for attr in ("joint_positions", "joint_velocities", "joint_efforts"):
                value = getattr(control_actions, attr, None)
                if value is not None:
                    fields[attr] = np.asarray(value).tolist()
            indices = control_actions.joint_indices
            indices = list(range(len(self.names[side]))) if indices is None else np.asarray(indices).tolist()
            command = {"command_id": str(uuid.uuid4()), "phase": get_phase(),
                       "arm": side, "runtime_indices": indices,
                       "channels": [self.names[side][i] for i in indices],
                       "targets": fields, "position_representation": "absolute",
                       "observation_id": obs["observation_id"], "issue": self.clock(),
                       "feedback_observation_id": None}
            result = original(control_actions)
            command["api_returned"] = self.clock()
            self.actions.append(command)
            self.pending_feedback.append(command)
            return result
        return apply

    def save(self, condition):
        frames = self.output / "rgb-frames.npz"
        rgb = np.stack(self.frames)
        with frames.open("xb") as stream:
            np.savez_compressed(stream, rgb=rgb)
        digest = sha256_file(frames)
        evidence = {"schema": "garment-observation-trace-v1", "trial_id": self.trial_id,
                    "condition": condition, "scope": "first_sleeve_component_exploration",
                    "clock_domains": {"sim_time_s": "Isaac including RGB render time",
                                      "wall_monotonic_ns": "local Python monotonic clock"},
                    "target_units": {"joint_positions": "rad", "joint_velocities": "rad/s", "joint_efforts": "N*m"},
                    "joint_names_runtime_order": self.names,
                    "frame_archive": {"file": frames.name, "bytes": frames.stat().st_size, "sha256": digest,
                                      "array": "rgb", "dtype": "uint8", "shape": list(rgb.shape)},
                    "observations": self.observations, "actions": self.actions, "boundaries": self.boundaries}
        (self.output / "observation-trace.json").write_text(
            json.dumps(evidence, separators=(",", ":"), allow_nan=False), encoding="utf-8")
