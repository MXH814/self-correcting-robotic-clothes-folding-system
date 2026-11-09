"""Offline packets matching the RGB interface handed to Ma's online detector.

No injection tags, final judgment or class labels are exposed by this reader.
One trial is loaded at a time; callers release the iterator before opening another.
"""
import json
from pathlib import Path
import numpy as np


def iter_observations(trial_directory):
    root = Path(trial_directory)
    trace = json.loads((root / "observation-trace.json").read_text(encoding="utf-8"))
    context = json.loads((root / "continuation-context.json").read_text(encoding="utf-8"))
    if trace["trial_id"] != context["trial_id"]:
        raise ValueError("Cross-trial camera context")
    with np.load(root / "rgb-frames.npz", allow_pickle=False) as archive:
        rgb = archive["rgb"]
    for observation in trace["observations"]:
        yield {"trial_id": trace["trial_id"], "observation_id": observation["observation_id"],
               "rgb": rgb[observation["frame_index"]], "frame_index": observation["frame_index"],
               "rendering_time_s": observation["rendering_time_s"],
               "capture_clock": observation["joint_read_end"], "phase": observation["phase"],
               "joint_state": observation["joint_state"],
               "camera_reference": context["camera"], "encoder_ref": None}
