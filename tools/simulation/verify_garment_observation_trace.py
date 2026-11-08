"""Check a downloaded garment trial without launching Isaac Sim."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(root):
    trace = json.loads((root / "observation-trace.json").read_text(encoding="utf-8"))
    physical = json.loads((root / "fault-evidence.json").read_text(encoding="utf-8"))
    trial, = physical["trials"]
    require(trial["trial_id"] == trace["trial_id"], "Trial identifiers differ")
    require(trial["condition"] == trace["condition"], "Trial conditions differ")

    frames = trace["frame_archive"]
    archive = root / "rgb-frames.npz"
    with archive.open("rb") as stream:
        require(hashlib.file_digest(stream, "sha256").hexdigest() == frames["sha256"], "RGB SHA256 mismatch")
    require(archive.stat().st_size == frames["bytes"], "RGB archive length mismatch")
    with np.load(archive, allow_pickle=False) as loaded:
        rgb = loaded["rgb"]
        require(list(rgb.shape) == frames["shape"] and rgb.dtype == np.uint8, "Unexpected RGB shape or dtype")
        require(rgb.ndim == 4 and rgb.shape[-1] == 3, "Expected NHWC RGB array")
        require(np.all(rgb.max(axis=(1, 2, 3)) > rgb.min(axis=(1, 2, 3))), "Uniform RGB frame")
    observations = {obs["observation_id"]: obs for obs in trace["observations"]}
    require(len(observations) == len(trace["observations"]), "Duplicate observation ID")
    require({obs["frame_index"] for obs in observations.values()} == set(range(len(rgb))),
            "RGB frame indices are not fully covered")
    render_times = {}
    for obs in observations.values():
        t = obs["rendering_time_s"]
        require(render_times.setdefault(obs["frame_index"], t) == t, "Inconsistent render timestamp")
        require(t <= obs["camera_read_begin"]["sim_time_s"] + 1e-7, "Render occurred after read")
        require(obs["camera_read_begin"]["wall_monotonic_ns"] <= obs["camera_read_end"]["wall_monotonic_ns"]
                <= obs["joint_read_end"]["wall_monotonic_ns"], "Observation reads out of order")
        for arm, names in trace["joint_names_runtime_order"].items():
            state = obs["joint_state"][arm]
            require(all(len(state[field]) == len(names) and np.isfinite(state[field]).all()
                        for field in ("position_rad", "velocity_rad_s")), "Invalid named joint state")
    actions = trace["actions"]
    require(len({a["command_id"] for a in actions}) == len(actions) > 0, "Missing or duplicate commands")
    for action in actions:
        source = observations[action["observation_id"]]
        feedback = observations[action["feedback_observation_id"]]
        issue = action["issue"]
        returned = action["api_returned"]
        require(source["joint_read_end"]["wall_monotonic_ns"] <= issue["wall_monotonic_ns"]
                <= returned["wall_monotonic_ns"] <= feedback["camera_read_begin"]["wall_monotonic_ns"],
                "Command and feedback reads out of order")
        require(source["joint_read_end"]["sim_step"] <= issue["sim_step"] < feedback["camera_read_begin"]["sim_step"],
                "Feedback must come from a later simulation step")
        names = trace["joint_names_runtime_order"][action["arm"]]
        require([names[i] for i in action["runtime_indices"]] == action["channels"], "Joint names mismatch")
        require(action["targets"] and all(len(value) == len(action["channels"])
                                          for value in action["targets"].values()), "Invalid target vector")
    for boundary in trace["boundaries"]:
        require(observations[boundary["observation_id"]]["phase"] == boundary["phase"], "Phase mismatch")
    intervals = np.diff([render_times[index] for index in range(len(rgb))])
    require(len(intervals) and np.all(intervals > 0), "RGB render times are not strictly increasing")
    return {"trial_id": trial["trial_id"], "condition": trial["condition"], "rgb_frames": len(rgb),
            "observations": len(observations), "actual_dispatches_with_feedback": len(actions),
            "maximum_render_gap_sim_s": float(intervals.max())}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trial_directory", type=Path, nargs="+")
    args = parser.parse_args()
    print(json.dumps([verify(path) for path in args.trial_directory], indent=2))
