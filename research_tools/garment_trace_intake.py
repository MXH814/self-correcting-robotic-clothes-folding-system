"""Causal, offline garment inputs; SDK dispatches are not recovery candidates.

Only declared RGB and joint/action observations become features. Conditions,
injection phases, hidden cloth geometry and subsequent outcomes stay out.
"""
import argparse
import hashlib
import json
from pathlib import Path

from .diagnostics import finite, require
from .legacy_features import rgb_grid
from .runtime_intake import clock, digest, ordered


def verify_files(directory):
    root = Path(directory).resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    entries = manifest.get("files")
    require(isinstance(entries, list) and 1 <= len(entries) <= 200, "invalid manifest files")
    names = [e["file"] for e in entries]
    require(len(names) == len(set(names)), "duplicate manifest member")
    for item in entries:
        name = item["file"]
        require(isinstance(name, str) and name not in (".", "..")
                and "/" not in name and "\\" not in name, "unsafe manifest member")
        path = (root / name).resolve()
        require(path.parent == root and path.is_file(), "missing/outside manifest member")
        require(type(item.get("bytes")) is int and 0 <= item["bytes"] <= 256 * 1024 * 1024,
                "invalid member size")
        require(path.stat().st_size == item["bytes"] and digest(path) == item["sha256"],
                "member fingerprint mismatch: " + name)
    return manifest


def joint_vector(observation, names):
    values = []
    for field in ("position_rad", "velocity_rad_s"):
        for arm in ("left", "right"):
            vector = observation["joint_state"][arm][field]
            require(isinstance(vector, list) and len(vector) == len(names[arm])
                    and all(finite(v) for v in vector), "invalid named joint state")
            values.extend(vector)
    return values


def encode_target(action, observation, names):
    """Masked multijoint absolute position targets; no DR04/limit claim."""
    require(action.get("position_representation") == "absolute"
            and set(action["targets"]) == {"joint_positions"}, "unsupported action semantics")
    arm = action["arm"]
    require(arm in names, "unknown action arm")
    indices = action["runtime_indices"]
    require(isinstance(indices, list) and bool(indices) and len(set(indices)) == len(indices)
            and all(type(i) is int and 0 <= i < len(names[arm]) for i in indices), "invalid action indices")
    require(action["channels"] == [names[arm][i] for i in indices], "action channel mismatch")
    targets = action["targets"]["joint_positions"]
    require(len(targets) == len(indices) and all(finite(v) for v in targets), "invalid action targets")
    n = sum(len(v) for v in names.values())
    q = joint_vector(observation, names)[:n]
    mask, absolute, delta = [0.] * n, [0.] * n, [0.] * n
    offset = 0 if arm == "left" else len(names["left"])
    for i, target in zip(indices, targets):
        k = offset + i
        mask[k], absolute[k], delta[k] = 1., target, target - q[k]
    return mask + absolute + delta


def validate_trace(trace, rgb, position_unit_source=None):
    import numpy as np
    require(trace.get("schema") == "garment-observation-trace-v1", "unsupported trace schema")
    require(isinstance(trace.get("trial_id"), str) and bool(trace["trial_id"]), "missing trial ID")
    names = trace["joint_names_runtime_order"]
    require(set(names) == {"left", "right"}, "expected two named arms")
    for values in names.values():
        require(isinstance(values, list) and len(values) > 0
                and all(isinstance(v, str) and v for v in values)
                and len(set(values)) == len(values), "invalid joint names")
    units = trace.get("target_units", {}).get("joint_positions")
    require(units == "rad" or (units is None and isinstance(position_unit_source, str)
                              and bool(position_unit_source.strip())), "missing position-unit declaration")
    require(rgb.dtype == np.uint8 and rgb.ndim == 4 and rgb.shape[-1] == 3
            and list(rgb.shape) == trace["frame_archive"]["shape"], "invalid RGB archive")
    require(np.all(rgb.max(axis=(1, 2, 3)) > rgb.min(axis=(1, 2, 3))), "uniform RGB frame")
    observations, actions = trace["observations"], trace["actions"]
    require(bool(observations) and bool(actions), "empty trace")
    ids = [o["observation_id"] for o in observations]
    require(all(isinstance(x, str) and x for x in ids) and len(ids) == len(set(ids)), "observation IDs")
    index = {value: i for i, value in enumerate(ids)}
    frames = {}
    previous = None
    for o in observations:
        a, b, c = [clock(o[k]) for k in ("camera_read_begin", "camera_read_end", "joint_read_end")]
        require(ordered(a, b) and ordered(b, c), "observation read order")
        require(previous is None or ordered(previous, a), "observation chronology")
        previous = c
        f, t = o["frame_index"], o["rendering_time_s"]
        require(type(f) is int and 0 <= f < len(rgb), "invalid frame index")
        require(finite(t) and 0 <= t <= a["sim_time_s"] + 1e-7, "future/invalid rendered frame")
        require(frames.setdefault(f, t) == t, "inconsistent render timestamp")
        joint_vector(o, names)
    require(set(frames) == set(range(len(rgb))), "uncovered RGB frames")
    require(all(frames[i] < frames[i+1] for i in range(len(rgb)-1)), "render chronology")
    command_ids = [a["command_id"] for a in actions]
    require(all(isinstance(x, str) and x for x in command_ids)
            and len(command_ids) == len(set(command_ids)), "command IDs")
    previous = None
    for action in actions:
        require(action["observation_id"] in index and action["feedback_observation_id"] in index,
                "command observation reference")
        before = observations[index[action["observation_id"]]]
        after = observations[index[action["feedback_observation_id"]]]
        issue, returned = clock(action["issue"]), clock(action["api_returned"])
        require(ordered(before["joint_read_end"], issue) and ordered(issue, returned)
                and ordered(returned, after["camera_read_begin"]), "command/feedback chronology")
        require(previous is None or ordered(previous, issue), "dispatch chronology")
        previous = returned
        require(issue["sim_step"] < after["camera_read_begin"]["sim_step"], "feedback must follow a step")
        encode_target(action, before, names)
    return index


def _padded(vectors, length, dimension):
    vectors = vectors[-length:]
    padding = length - len(vectors)
    return [0.] * (padding * dimension) + [x for v in vectors for x in v], [False] * padding + [True] * len(vectors)


def encode_trace(trace, rgb, history=4, grid=8, position_unit_source=None):
    require(type(history) is int and 1 <= history <= 32, "history must be 1..32")
    indices = validate_trace(trace, rgb, position_unit_source)
    names, observations, actions = trace["joint_names_runtime_order"], trace["observations"], trace["actions"]
    n = sum(map(len, names.values()))
    profile = [arm + ":" + name for arm in ("left", "right") for name in names[arm]]
    profile_id = hashlib.sha256(json.dumps(profile, separators=(",", ":")).encode()).hexdigest()
    visuals = [rgb_grid(frame, grid) for frame in rgb]
    joint = [joint_vector(o, names) for o in observations]
    targets = [encode_target(a, observations[indices[a["observation_id"]]], names) for a in actions]
    rows = []
    for ai, action in enumerate(actions):
        oi = indices[action["observation_id"]]
        source = observations[oi]
        # One past observation per older rendered frame, selected from the prefix only.
        older = {}
        for i, o in enumerate(observations[:oi]):
            if o["frame_index"] < source["frame_index"]:
                older[o["frame_index"]] = i
        past_indices = list(older.values())[-history:]
        obs_vectors = [visuals[observations[i]["frame_index"]] + joint[i] for i in past_indices]
        past, obs_mask = _padded(obs_vectors, history, len(visuals[0]) + 2*n)
        prior = []
        for j, candidate in enumerate(actions[:ai]):
            fi = indices[candidate["feedback_observation_id"]]
            if fi <= oi and ordered(observations[fi]["joint_read_end"], source["joint_read_end"]):
                delta = [b-a for a,b in zip(joint[indices[candidate["observation_id"]]][:n], joint[fi][:n])]
                elapsed = observations[fi]["joint_read_end"]["sim_time_s"] - candidate["issue"]["sim_time_s"]
                prior.append((candidate["command_id"], targets[j] + delta + [elapsed]))
        executed, action_mask = _padded([v for _,v in prior], history, 4*n+1)
        rows.append({"schema": "garment-dispatch-input/1", "trial_id": trace["trial_id"],
                     "command_id": action["command_id"], "observation_id": source["observation_id"],
                     "as_of": action["issue"], "source_frame_index": source["frame_index"],
                     "profile_id": profile_id, "channel_order": profile,
                     "current_observation": visuals[source["frame_index"]] + joint[oi],
                     "candidate_target": targets[ai],
                     "past_observations": past, "observation_history_mask": obs_mask,
                     "past_observation_ids": [observations[i]["observation_id"] for i in past_indices],
                     "executed_history": executed, "action_history_mask": action_mask,
                     "past_command_ids": [k for k,_ in prior[-history:]],
                     "stage_budget": None, "recovery_macro_candidate_spec": None,
                     "input_scope": "recorded absolute articulation target; not a recovery candidate pool",
                     "feedback_scope": "later shared observation; not isolated per-command physical effect",
                     "local_success": None, "autonomous_success": None, "online_authorized": False})
    report = {"trial_id": trace["trial_id"], "observations": len(observations), "rgb_frames": len(rgb),
              "dispatch_inputs": len(rows), "channels": n, "history_length": history,
              "dimensions": {"current_observation": len(rows[0]["current_observation"]),
                             "candidate_target": 3*n, "past_observations": len(rows[0]["past_observations"]),
                             "executed_history": len(rows[0]["executed_history"])},
              "inputs_with_prior_observations": sum(any(r["observation_history_mask"]) for r in rows),
              "inputs_with_completed_prior_commands": sum(any(r["action_history_mask"]) for r in rows),
              "verified_recovery_labels": 0, "online_authorized": False,
              "position_unit_declaration": ("trace_metadata" if trace.get("target_units")
                                             else position_unit_source),
              "recovery_training_ready": False, "research_conclusion": "NOT_ESTABLISHED"}
    return rows, report


def export_trace(directory, output, history=4, grid=8, position_unit_source=None):
    import numpy as np
    root, output = Path(directory).resolve(), Path(output).resolve()
    require(root != output and root not in output.parents, "output must be outside evidence")
    require(not output.exists(), "output already exists")
    manifest = verify_files(root)
    trace = json.loads((root / "observation-trace.json").read_text(encoding="utf-8"))
    require(manifest["trial_id"] == trace["trial_id"], "cross-trial manifest")
    require(trace["frame_archive"]["file"] == "rgb-frames.npz"
            and digest(root / "rgb-frames.npz") == trace["frame_archive"]["sha256"], "RGB binding")
    with np.load(root / "rgb-frames.npz", allow_pickle=False) as data:
        rows, report = encode_trace(trace, data["rgb"], history, grid, position_unit_source)
    report.update(source_manifest_sha256=digest(root / "manifest.json"),
                  source_trace_sha256=digest(root / "observation-trace.json"), producer_sha256=digest(__file__))
    output.mkdir(parents=True)
    with (output / "dispatch-inputs.jsonl").open("x", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n")
    (output / "audit.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--history", type=int, default=4)
    parser.add_argument("--position-unit-source", help="Explicit radian SDK declaration reference for older traces without target_units")
    args = parser.parse_args()
    print(json.dumps(export_trace(args.input_dir, args.output_dir, args.history,
                                 position_unit_source=args.position_unit_source), indent=2))


if __name__ == "__main__":
    main()
