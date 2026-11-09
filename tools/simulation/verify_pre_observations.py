"""Verify a normal trace, and export the observation/time/stage interchange index."""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from research_tools.garment_trace_intake import verify_files, validate_trace


def audit(root, output):
    root, output = Path(root), Path(output)
    manifest = verify_files(root)
    trace = json.loads((root / "observation-trace.json").read_text(encoding="utf-8"))
    record = json.loads((root / "full-fold-recovery.json").read_text(encoding="utf-8"))
    context = json.loads((root / "continuation-context.json").read_text(encoding="utf-8"))
    assert manifest["trial_id"] == trace["trial_id"] == record["trial_id"] == context["trial_id"]
    assert trace["scope"] == "complete_fold_tops_normal_collection"
    assert record["injection"] is None and not record["recovery_enabled"]
    assert not record.get("macro_execution")
    phases = {x["phase"] for x in trace["boundaries"]}
    assert {f"upstream-stage-{i}-end" for i in (1, 2, 3)} <= phases
    assert "normal-planned-release" in phases
    with np.load(root / "rgb-frames.npz", allow_pickle=False) as archive:
        rgb = archive["rgb"]
    validate_trace(trace, rgb)
    output.mkdir(parents=True, exist_ok=False)
    Image.fromarray(rgb[0]).save(output / "sample-first.png")
    Image.fromarray(rgb[-1]).save(output / "sample-final.png")
    times = sorted({o["rendering_time_s"] for o in trace["observations"]})
    report = {"trial_id": trace["trial_id"], "source": str(root.resolve()),
              "rgb_shape": list(rgb.shape), "rgb_dtype": str(rgb.dtype),
              "observations": len(trace["observations"]), "dispatches": len(trace["actions"]),
              "max_rgb_gap_sim_s": float(np.diff(times).max()), "camera": context["camera"],
              "joint_names": trace["joint_names_runtime_order"], "visual_embedding": None,
              "proprioception_dimensions": 120, "recovery_enabled": False,
              "upstream_proxy": record["judgment"], "detector_status": "UNKNOWN",
              "independent_review": "pending", "dataset_use": "unassigned"}
    (output / "audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (output / "observation-sample.json").write_text(json.dumps(trace["observations"][0], indent=2), encoding="utf-8")
    (output / "camera.json").write_text(json.dumps(context["camera"], indent=2), encoding="utf-8")
    with (output / "observations.jsonl").open("w", encoding="utf-8") as stream:
        for obs in trace["observations"]:
            stream.write(json.dumps({"schema": "pre-observation/1", "trial_id": trace["trial_id"],
                "observation_id": obs["observation_id"], "rgb_archive": str(root / "rgb-frames.npz"),
                "rgb_key": "rgb", "frame_index": obs["frame_index"], "phase": obs["phase"],
                "rendering_time_s": obs["rendering_time_s"], "capture_clock": obs["joint_read_end"],
                "joint_state": obs["joint_state"], "camera_reference": "camera.json",
                "visual_embedding": None, "encoder_ref": None}, separators=(",", ":")) + "\n")
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("root", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    print(json.dumps(audit(a.root, a.output), indent=2))
