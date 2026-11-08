"""Verify archived numeric midstate snapshots and independently recalculate their errors."""
import argparse
import hashlib
import io
import json
from pathlib import Path

import numpy as np


FIELDS = ("vertices_m", "vertex_velocity_m_s", "joint_position_rad", "joint_velocity_rad_s")


def load_snapshot(directory, entry):
    name = entry["file"]
    if Path(name).name != name or "/" in name or "\\" in name:
        raise ValueError(f"Snapshot name must be local to the evidence directory: {name}")
    raw = (directory / name).read_bytes()
    if len(raw) != entry["bytes"] or hashlib.sha256(raw).hexdigest() != entry["sha256"]:
        raise ValueError(f"Snapshot fingerprint mismatch: {name}")
    with np.load(io.BytesIO(raw), allow_pickle=False) as archive:
        if set(archive.files) != set(FIELDS):
            raise ValueError(f"Unexpected arrays in {name}")
        arrays = {key: archive[key] for key in FIELDS}
    for key, value in arrays.items():
        if not np.issubdtype(value.dtype, np.floating) or not np.isfinite(value).all():
            raise ValueError(f"Invalid numeric data for {key} in {name}")
    vertices = arrays["vertices_m"]
    if (vertices.ndim != 2 or vertices.shape[0] == 0 or vertices.shape[1] != 3
            or arrays["vertex_velocity_m_s"].shape != vertices.shape
            or arrays["joint_position_rad"].shape != (60,)
            or arrays["joint_velocity_rad_s"].shape != (60,)):
        raise ValueError(f"Unexpected shape in {name}")
    return arrays


def audit(evidence_path):
    evidence = json.loads(evidence_path.read_bytes())
    names = evidence["midstate_joint_names"]
    if any(len(names[side]) != 30 or len(set(names[side])) != 30 for side in ("left", "right")):
        raise ValueError("Expected 30 distinct joint names on each side")
    trials = evidence["trials"]
    if not trials:
        raise ValueError("Evidence contains no trials")
    if any("midstate_snapshot" not in trial for trial in trials):
        raise ValueError("Evidence is incomplete; a trial has no midstate snapshot")
    if len({trial["midstate_snapshot"]["file"] for trial in trials}) != len(trials):
        raise ValueError("Each trial must have its own snapshot")
    reference = load_snapshot(evidence_path.parent, trials[0]["midstate_snapshot"])
    audited = []
    for trial in trials:
        entry = trial["midstate_snapshot"]
        if entry["sim_time_s"] != trial["midstate_sim_time_s"]:
            raise ValueError(f"Snapshot time does not match trial {trial['case_index']}")
        arrays = load_snapshot(evidence_path.parent, entry)
        errors = {}
        for key, original in reference.items():
            if arrays[key].shape != original.shape:
                raise ValueError(f"Shape differs from reference for {key} in {entry['file']}")
            delta = arrays[key].astype(np.float64) - original.astype(np.float64)
            error = np.linalg.norm(delta, axis=1) if delta.ndim == 2 else np.abs(delta)
            reported = trial["midstate_error_vs_first"][key]
            values = {"max_abs": float(error.max()), "rms": float(np.sqrt(np.mean(np.square(error))))}
            if any(not np.isclose(value, reported[name], rtol=1e-6, atol=1e-12)
                   for name, value in values.items()):
                raise ValueError(f"Recorded error mismatch for {key} in {entry['file']}")
            errors[key] = values
        audited.append({"case_index": trial["case_index"], "snapshot": entry["file"],
                        "vertex_count": reference["vertices_m"].shape[0], "errors": errors})
    return audited


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path, help="fault-evidence.json next to the numeric snapshots")
    args = parser.parse_args()
    print(json.dumps(audit(args.evidence), indent=2, allow_nan=False))
