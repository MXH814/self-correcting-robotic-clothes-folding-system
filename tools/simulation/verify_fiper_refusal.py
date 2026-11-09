"""Audit actual missing-RND-OE refusal evidence; do not imply physical stop proof."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from research_tools.garment_trace_intake import verify_files, validate_trace


def audit(root):
    root = Path(root)
    manifest = verify_files(root)
    record = json.loads((root / "full-fold-recovery.json").read_text(encoding="utf-8"))
    trace = json.loads((root / "observation-trace.json").read_text(encoding="utf-8"))
    assert manifest["trial_id"] == record["trial_id"] == trace["trial_id"]
    with np.load(root / "rgb-frames.npz", allow_pickle=False) as archive:
        rgb = archive["rgb"]
    validate_trace(trace, rgb)
    assert record["final_control_state"] == "HELP_REQUESTED_AUTOMATIC_DISPATCH_DISABLED"
    official = record.get("pre_scenario") == "C_official_missing_package"
    from research_tools.observation_detector import METHOD
    assert record["fiper_report"]["method"] == (METHOD if official else "FIPER-RND-OE-observation-adaptation")
    assert record["fiper_report"]["status"] == "UNKNOWN"
    assert not ({"action_preds", "policy_checkpoint_ref"} & set(record["fiper_report"].get("missing", [])))
    assert record["judgment"] is None and record["recovery_attempts"] == 0
    assert not record.get("macro_execution") and not record["fixed_continuation_started"]
    assert record["dispatch_count_at_help"] == record["dispatch_count_at_exit"] == len(trace["actions"])
    events = [json.loads(line) for line in (root / "pre-demo-events.jsonl").read_text(encoding="utf-8").splitlines()]
    help_event, = [e for e in events if e["kind"] == "HELP_REQUESTED"]
    if official:
        config = json.loads((root / "official-pre-config.json").read_text(encoding="utf-8"))
        assert config["trial_id"] == record["trial_id"]
        for name, digest in config["producer_sha256"].items():
            assert hashlib.sha256((root / "source-snapshot" / name).read_bytes()).hexdigest() == digest
        assert record["detection_entry"] == "OfficialPreAdapter/DetectionRuntime"
        detection, = [e for e in events if e["kind"] == "OFFICIAL_DETECTION"]
        assert detection["report"] == record["fiper_report"]
        from research_tools.observation_detector import FIELDS
        assert set(detection["observation"]) == FIELDS - {"embedding"}
        obs, = [o for o in trace["observations"]
                if o["observation_id"] == detection["observation"]["observation_id"]]
        assert detection["observation"]["frame_id"] == str(obs["rendering_frame"])
        assert detection["report"]["captured_wall_s"] == obs["camera_read_begin"]["wall_monotonic_ns"] / 1e9
        assert detection["report"]["reason"] == "MODEL_OR_CALIBRATION_UNAVAILABLE"
        assert detection["report"]["score"] is None
        journal = [json.loads(line) for line in (root / "official-workflow-events.jsonl").read_text(encoding="utf-8").splitlines()]
        assert journal[-1] == detection["request"]
        assert journal[-1]["kind"] == "REQUEST_HALT_AND_HELP"
        assert not any(e["kind"] == "MACRO_ACCEPTED" for e in journal)
    assert all(a["issue"]["wall_monotonic_ns"] <= help_event["clock"]["wall_monotonic_ns"] for a in trace["actions"])
    return {"trial_id": record["trial_id"], "rgb_frames": len(rgb), "observations": len(trace["observations"]),
            "dispatches_before_refusal": len(trace["actions"]), "dispatches_after_refusal": 0,
            "recovery_attempts": 0, "detector_status": "UNKNOWN", "fiper_scores_computed": False,
            "missing": record["fiper_report"].get("missing", [record["fiper_report"].get("reason")]),
            "official_runtime_executed": official, "physical_rest_verified": False,
            "scope": "actual simulation, unavailable observation detector -> no new dispatch",
            "final_state": record["final_control_state"], "independent_review": "pending"}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("root", type=Path)
    p.add_argument("--output", type=Path)
    a = p.parse_args()
    report = audit(a.root)
    if a.output:
        with a.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2)
    print(json.dumps(report, indent=2))
