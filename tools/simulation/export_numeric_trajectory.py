"""Export a trusted legacy Fold_Tops NPZ to numeric observations, never recovery labels.

NumPy is required. Object-array loading uses pickle: a hash does not establish trust.
Use only on an independently trusted archive, preferably on the collection machine.
"""
import argparse
import hashlib
import json
from pathlib import Path


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def export(source, output, expected_sha256, trusted=False, max_source_bytes=256 * 1024**2):
    if not trusted:
        raise ValueError("independent source trust required; SHA256 alone is not trust")
    source, output = Path(source), Path(output)
    if output.exists():
        raise FileExistsError("output directory already exists; no overwrite")
    if source.stat().st_size > max_source_bytes:
        raise ValueError("archive exceeds the small legacy-import size limit")
    actual = sha256(source)
    if actual.lower() != expected_sha256.lower():
        raise ValueError("source hash mismatch; refusing to deserialize")
    import numpy as np
    # All records are validated before writing. Only independently trusted objects may reach here.
    prepared = []
    with np.load(source, allow_pickle=True) as archive:
        for stage in ("stage_1", "stage_2", "stage_3"):
            if stage not in archive:
                raise ValueError("missing stage: " + stage)
            records = archive[stage]
            if records.ndim != 1 or len(records) == 0:
                raise ValueError("expected nonempty 1D stage records")
            for index, record in enumerate(records):
                if not isinstance(record, dict):
                    raise ValueError("stage record is not a mapping")
                joints = np.asarray(record.get("joint_state"))
                image = np.asarray(record.get("image"))
                if joints.shape != (60,) or joints.dtype.kind not in "fi" or not np.isfinite(joints).all():
                    raise ValueError("expected 60 finite joint positions; channel semantics remain unverified")
                if (image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3
                        or min(image.shape[:2]) < 1):
                    raise ValueError("expected nonempty uint8 HxWx3 image")
                prepared.append((stage, index, joints.tolist(), image.copy()))
    output.mkdir(parents=True, exist_ok=False)
    (output / "rgb").mkdir()
    rows = []
    for stage, index, joints, image in prepared:
        relative = "rgb/%s-%06d.npy" % (stage, index)
        with (output / relative).open("xb") as f:
            np.save(f, image, allow_pickle=False)
        rows.append({"schema_version": "legacy-fold-observation/1", "trajectory_id": actual,
                     "frame_id": "%s/%s/%d" % (actual, stage, index), "stage": stage,
                     "index": index, "history_gap_before": index == 0,
                     "source_kind": "legacy_demonstration", "joint_state": joints,
                     "joint_mapping_verified": False, "joint_units_verified": False,
                     "rgb": {"path": relative, "sha256": sha256(output / relative),
                             "shape": list(image.shape), "dtype": "uint8",
                             "source": "record.image", "camera_provenance_verified": False},
                     "sim_time_s": None, "wall_monotonic_s": None, "action": None,
                     "command_id": None, "action_ack": None,
                     "local_success": None, "autonomous_success": None,
                     "online_authorized": False})
    records_path = output / "observations.jsonl"
    with records_path.open("x", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    manifest = {"schema_version": "legacy-fold-export/1", "status": "EXPORT_COMPLETE",
                "source_sha256": actual, "source_file_bytes": source.stat().st_size,
                "purpose": "legacy_demo_import", "frames": len(rows),
                "stage_counts": {s: sum(r["stage"] == s for r in rows) for s in ("stage_1", "stage_2", "stage_3")},
                "records_sha256": sha256(records_path), "online_authorized": False,
                "note": "No timestamps or dispatched actions reconstructed; no point-cloud/affordance input exported; no outcome labels inferred. Manifest is written last. Missing manifest means incomplete export."}
    with (output / "manifest.json").open("x", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False, allow_nan=False)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--trusted-object-source", action="store_true")
    args = parser.parse_args()
    result = export(args.input, args.output_dir, args.sha256, args.trusted_object_source)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
