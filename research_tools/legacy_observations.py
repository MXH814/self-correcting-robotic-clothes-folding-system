"""Verify numeric legacy exports and build bounded, stage-local offline history."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from .diagnostics import finite, require


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def validate_rows(rows):
    require(bool(rows), "empty observations")
    previous, seen, closed = None, set(), set()
    for r in rows:
        require(r.get("schema_version") == "legacy-fold-observation/1", "wrong schema")
        require(r.get("source_kind") == "legacy_demonstration", "not a legacy demonstration")
        require(isinstance(r.get("trajectory_id"), str) and re.fullmatch(r"[a-f0-9]{64}", r["trajectory_id"]), "bad source hash")
        require(r.get("stage") in ("stage_1", "stage_2", "stage_3"), "unknown stage")
        require(type(r.get("index")) is int and r["index"] >= 0, "bad index")
        key = (r["trajectory_id"], r["stage"])
        same = previous is not None and key == (previous["trajectory_id"], previous["stage"])
        if not same:
            require(key not in closed and r["index"] == 0, "interleaved/reopened segment or nonzero first index")
            closed.add(key)
        else:
            require(r["index"] == previous["index"] + 1, "non-contiguous frame indices")
        expected = "%s/%s/%d" % (r["trajectory_id"], r["stage"], r["index"])
        require(r.get("frame_id") == expected and expected not in seen, "bad/duplicate frame id")
        seen.add(expected)
        require(r.get("history_gap_before") is (not same), "stage boundary must reset history")
        joints = r.get("joint_state")
        require(isinstance(joints, list) and len(joints) == 60 and all(finite(x) for x in joints), "invalid joints")
        require(r.get("joint_mapping_verified") is False and r.get("joint_units_verified") is False,
                "legacy import cannot attest channel semantics")
        require(r.get("online_authorized") is False, "legacy observations cannot authorize online use")
        for field in ("sim_time_s", "wall_monotonic_s", "action", "command_id", "action_ack",
                      "local_success", "autonomous_success"):
            require(field in r and r[field] is None, "legacy field must stay unknown: " + field)
        rgb = r.get("rgb", {})
        require(rgb.get("path") == "rgb/%s-%06d.npy" % (r["stage"], r["index"]), "unexpected RGB reference")
        require(isinstance(rgb.get("sha256"), str) and re.fullmatch(r"[a-f0-9]{64}", rgb["sha256"]), "bad RGB hash")
        require(rgb.get("camera_provenance_verified") is False, "unverified camera source")
        require(not any(k in r for k in ("garment_point_cloud", "env_point_cloud", "points_affordance_feature")),
                "unapproved feature source")
        previous = r
    return rows


def load_export(directory):
    import numpy as np
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    require(manifest.get("schema_version") == "legacy-fold-export/1" and manifest.get("status") == "EXPORT_COMPLETE",
            "incomplete/unknown export")
    records = directory / "observations.jsonl"
    require(digest(records) == manifest.get("records_sha256"), "records hash mismatch")
    rows = validate_rows([json.loads(x) for x in records.read_text(encoding="utf-8").splitlines() if x.strip()])
    require(len(rows) == manifest.get("frames"), "frame count mismatch")
    require({r["trajectory_id"] for r in rows} == {manifest.get("source_sha256")}, "source mismatch")
    actual_counts = {s: sum(r["stage"] == s for r in rows) for s in ("stage_1", "stage_2", "stage_3")}
    require(actual_counts == manifest.get("stage_counts") and all(actual_counts.values()), "stage counts mismatch")
    require(manifest.get("online_authorized") is False, "invalid online permission")
    for r in rows:
        path = directory / r["rgb"]["path"]
        require(digest(path) == r["rgb"]["sha256"], "RGB hash mismatch")
        image = np.load(path, allow_pickle=False)
        require(image.dtype == np.uint8 and image.ndim == 3 and image.shape[2] == 3
                and list(image.shape) == r["rgb"].get("shape") and min(image.shape[:2]) > 0, "invalid numeric RGB")
    return rows


def history_window(rows, index, length=4):
    """Previous frames only, current excluded; indices are NOT measured elapsed time."""
    require(type(index) is int and 0 <= index < len(rows), "bad window index")
    require(type(length) is int and 1 <= length <= 64, "history length must be 1..64")
    current, previous = rows[index], []
    for j in range(index - 1, -1, -1):
        if rows[j]["trajectory_id"] != current["trajectory_id"] or rows[j]["stage"] != current["stage"]:
            break
        previous.append(rows[j])
        if len(previous) == length:
            break
    previous.reverse()
    missing = length - len(previous)
    return {"current_frame_id": current["frame_id"], "previous_frame_ids": [None] * missing + [r["frame_id"] for r in previous],
            "mask": [False] * missing + [True] * len(previous),
            "joint_history": [[0.] * 60 for _ in range(missing)] + [r["joint_state"] for r in previous],
            "rgb_history": [None] * missing + [r["rgb"] for r in previous],
            "action_history": None, "elapsed_time_known": False, "online_authorized": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--index", type=int, default=0)
    parser.add_argument("--history", type=int, default=4)
    args = parser.parse_args()
    rows = load_export(args.input_dir)
    print(json.dumps({"frames_verified": len(rows), "window": history_window(rows, args.index, args.history),
                      "research_conclusion": "NOT_ESTABLISHED"}, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
