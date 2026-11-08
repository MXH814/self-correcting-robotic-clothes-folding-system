"""Deterministic offline RGB/joint features for normal demonstration integration.

This is not recovery-candidate data, a learned visual encoder, or an online profile.
Requires the existing numeric export and NumPy; never loads object NPZ or pickle.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

from .diagnostics import require
from .legacy_observations import digest, history_window, load_export


def rgb_grid(image, grid=8):
    """Row-major RGB cell means in [0, 1]; no fitting or interpolation."""
    import numpy as np
    require(type(grid) is int and 1 <= grid <= 32, "grid must be an integer in 1..32")
    require(isinstance(image, np.ndarray) and image.dtype == np.uint8
            and image.ndim == 3 and image.shape[2] == 3, "expected uint8 RGB")
    height, width = image.shape[:2]
    require(min(height, width) >= grid, "image smaller than grid")
    ys, xs = np.linspace(0, height, grid + 1, dtype=int), np.linspace(0, width, grid + 1, dtype=int)
    cells = [image[ys[y]:ys[y + 1], xs[x]:xs[x + 1]].mean(axis=(0, 1), dtype=np.float64) / 255.
             for y in range(grid) for x in range(grid)]
    return np.asarray(cells, dtype=np.float32).reshape(-1).tolist()


def encode_export(directory, grid=8, history=4):
    import numpy as np
    require(type(history) is int and 1 <= history <= 64, "history must be an integer in 1..64")
    require(type(grid) is int and 1 <= grid <= 32, "grid must be an integer in 1..32")
    directory = Path(directory).resolve()
    rows = load_export(directory)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    cache, encoded = {}, []
    dimension = grid * grid * 3
    for index, row in enumerate(rows):
        # Cache contains only the already visited prefix, never future frames.
        current = rgb_grid(np.load(directory / row["rgb"]["path"], allow_pickle=False), grid)
        window = history_window(rows, index, history)
        past = [cache[f] if f is not None else [0.] * dimension for f in window["previous_frame_ids"]]
        encoded.append({
            "schema_version": "legacy-observation-features/1",
            "purpose": "offline_normal_observation",
            "feature_version": "rgb-grid-mean/1/g%d/h%d" % (grid, history),
            "trajectory_id": row["trajectory_id"], "frame_id": row["frame_id"],
            "stage": row["stage"], "index": row["index"],
            "source_rgb": row["rgb"],
            "current_rgb": current, "joint_raw": row["joint_state"],
            "past_rgb": [x for vector in past for x in vector],
            "past_joint_raw": [x for vector in window["joint_history"] for x in vector],
            "past_frame_ids": window["previous_frame_ids"], "history_mask": window["mask"],
            "action_history": None, "sim_time_s": None, "wall_monotonic_s": None,
            "candidate_id": None, "local_success": None, "autonomous_success": None,
            "joint_mapping_verified": False, "joint_units_verified": False,
            "camera_provenance_verified": False, "online_authorized": False,
        })
        cache[row["frame_id"]] = current
    meta = {"source_sha256": manifest["source_sha256"],
            "source_manifest_sha256": digest(directory / "manifest.json"),
            "source_records_sha256": manifest["records_sha256"],
            "frames": len(rows), "stage_counts": dict(Counter(r["stage"] for r in rows))}
    return encoded, meta


def export_features(input_dirs, output_dir, grid=8, history=4):
    require(bool(input_dirs), "at least one export required")
    output = Path(output_dir).resolve()
    require(all(output != Path(d).resolve() and Path(d).resolve() not in output.parents for d in input_dirs),
            "output must be outside input exports")
    if output.exists():
        raise FileExistsError(str(output))
    encoded, sources = [], []
    for directory in input_dirs:
        rows, meta = encode_export(directory, grid, history)
        require(meta["source_sha256"] not in {m["source_sha256"] for m in sources}, "duplicate source trajectory")
        sources.append(meta)
        encoded.extend(rows)
    # Validate all inputs before creating output. A completion manifest is written last.
    output.mkdir(parents=True, exist_ok=False)
    records = output / "features.jsonl"
    with records.open("x", encoding="utf-8", newline="\n") as stream:
        for row in encoded:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n")
    result = {
        "schema_version": "legacy-feature-export/1", "status": "EXPORT_COMPLETE",
        "purpose": "offline_normal_observation", "feature_version": encoded[0]["feature_version"],
        "frames": len(encoded), "sources": sources, "features_sha256": digest(records),
        "encoder": {"kind": "fixed spatial RGB means", "grid": [grid, grid],
                    "dimension": grid * grid * 3, "normalization": "uint8 / 255",
                    "order": "row-major cells, RGB within cell", "fitted_parameters": 0},
        "history": {"length": history, "current_excluded": True, "stage_local": True,
                    "zero_padding_with_explicit_mask": True, "record_order_only": True},
        "joint_dimension": 60, "joint_units_verified": False,
        "camera_provenance_verified": False, "online_authorized": False,
        "actions_available": False, "recovery_outcomes_available": False,
        "train_validation_split_created": False, "research_conclusion": "NOT_ESTABLISHED",
        "limitations": ["Normal observations only; no executed action or candidate representation.",
                        "No real elapsed time, stop evidence or verified runtime camera/joint profile.",
                        "Coarse pixel means are an integration baseline, not a learned visual model.",
                        "Do not convert frames into independent recovery trials or H1/H2 candidates."],
    }
    with (output / "manifest.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", action="append", required=True, help="Repeat for another numeric export")
    parser.add_argument("--output-dir", required=True, help="New output directory")
    parser.add_argument("--grid", type=int, default=8)
    parser.add_argument("--history", type=int, default=4)
    args = parser.parse_args()
    result = export_features(args.input_dir, args.output_dir, args.grid, args.history)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
