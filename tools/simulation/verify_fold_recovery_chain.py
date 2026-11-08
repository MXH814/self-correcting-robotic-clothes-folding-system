"""Audit a single full recovery run and export one UNREVIEWED macro feature row."""
import argparse
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from research_tools.diagnostics import require
from research_tools.garment_trace_intake import encode_trace, verify_files
from research_tools.recovery_candidates import encode_macro, recovery_features
from research_tools.runtime_intake import clock, digest, ordered
from verify_garment_observation_trace import verify_full_fold


def validate_binding(record, trace, proposal, decision, context):
    """Reject mixed trials, retrospective proposals and incomplete executions."""
    trial_id = record["trial_id"]
    require(all(item["trial_id"] == trial_id for item in (trace, proposal, decision, context)),
            "cross-trial recovery chain")
    require(trace["scope"] == "complete_fold_tops_diagnostic_recovery", "not a full-fold trace")
    require(decision["candidate_id"] == proposal["candidate_id"], "candidate identity mismatch")
    require(decision["lineage_group"] == trial_id, "unexpected lineage")
    encode_macro(proposal)
    require(ordered(clock(proposal["available_at"]), clock(decision["proposal_persisted_at"]))
            and ordered(clock(decision["proposal_persisted_at"]), clock(decision["decision_at"])),
            "retrospective or unpersisted proposal")
    observations = {o["observation_id"]: o for o in trace["observations"]}
    actions = {a["command_id"]: a for a in trace["actions"]}
    source = observations[decision["observation_id"]]
    require(ordered(source["joint_read_end"], decision["decision_at"]), "future decision observation")
    execution = record["macro_execution"]
    require([e["operation"] for e in execution] == ["release", "retreat", "regrasp", "close", "lift"],
            "incomplete or out-of-order macro")
    previous = decision["decision_at"]
    used = []
    for entry in execution:
        require(entry["candidate_id"] == proposal["candidate_id"], "execution candidate mismatch")
        require(ordered(previous, entry["begin"]) and ordered(entry["begin"], entry["end"]),
                "macro operation time order")
        require(bool(entry["command_ids"]), "macro operation has no actual dispatch")
        for identifier in entry["command_ids"]:
            require(identifier in actions and identifier not in used, "invalid/duplicate macro dispatch")
            action = actions[identifier]
            require(action["arm"] == proposal["arm"] and action["phase"] == "macro-" + entry["operation"],
                    "operation command arm/phase mismatch")
            require(ordered(entry["begin"], action["issue"])
                    and ordered(action["api_returned"], entry["end"]), "dispatch outside macro operation")
            used.append(identifier)
        if entry["operation"] in ("retreat", "regrasp", "lift"):
            require(entry["sdk_result"] is True, "macro IK did not complete")
            key = {"retreat": "retreat_world_m", "regrasp": "pick_world_m", "lift": "lift_world_m"}[entry["operation"]]
            require(entry["requested"]["target_world_m"] == proposal[key]
                    and entry["requested"]["orientation_wxyz"] == proposal["orientation_wxyz"]
                    and entry["requested"]["dense_sample_scale_m"] == context["controller"]["macro_motion_sample_scale_m"],
                    "executed macro target differs from proposal")
        else:
            require(entry["requested"] == {"hand_state": "open" if entry["operation"] == "release" else "close"},
                    "macro hand state mismatch")
        wait = proposal["open_wait_steps"] if entry["operation"] == "release" else (
            proposal["close_wait_steps"] if entry["operation"] == "close" else 0)
        require(entry["extra_wait_steps"] == wait and entry["end"]["sim_step"] - entry["begin"]["sim_step"] >= wait,
                "macro wait mismatch")
        previous = entry["end"]
    first = actions[used[0]]
    require(first["observation_id"] == decision["observation_id"]
            and ordered(decision["decision_at"], first["issue"]), "decision/first dispatch binding")
    phases = {b["phase"] for b in trace["boundaries"]}
    require({"upstream-stage-1-end", "upstream-stage-2-end", "upstream-stage-3-end",
             "fixed-upstream-continuation", "final-evidence"} <= phases, "incomplete continuation")
    require(record["resume_sdk_result"] is True, "resume IK failed")
    final = record["checkpoints"]["final"]
    require(previous["sim_step"] < final["sim_step"] and previous["sim_time_s"] < final["sim_time_s"],
            "final outcome predates macro completion")
    require(context["budget"]["diagnostic_macro_attempts"] == 1
            and context["budget"]["retry_count"] == 0, "unexpected diagnostic budget")
    require(context["target"]["minimum_ratio"] == record["judgment"]["minimum_ratio"], "target mismatch")
    require(decision["continuation_success"] is None and decision["label_review_reference"] is None,
            "capture must not sign its own independent label")
    return first["command_id"], len(used)


def audit(root, output=None):
    root = Path(root).resolve()
    manifest = verify_files(root)
    def read(name):
        return json.loads((root / name).read_text(encoding="utf-8"))
    record, trace = read("full-fold-recovery.json"), read("observation-trace.json")
    proposal, decision = read("macro-proposal.json"), read("recovery-decision.json")
    context = read("continuation-context.json")
    require(manifest["trial_id"] == record["trial_id"], "cross-trial manifest")
    for field, name in (("candidate_spec_reference", "macro-proposal.json"),
                        ("continuation_context_reference", "continuation-context.json")):
        require(decision[field] == name + "#sha256=" + digest(root / name), "reference hash mismatch")
    require(context["target"]["initial_point_cloud_sha256"] == digest(root / "initial-point-cloud.npz"),
            "initial point cloud mismatch")
    require(trace["frame_archive"]["sha256"] == digest(root / "rgb-frames.npz"), "RGB hash mismatch")
    first_command, macro_dispatches = validate_binding(record, trace, proposal, decision, context)
    final = verify_full_fold(root)
    with np.load(root / "rgb-frames.npz", allow_pickle=False) as data:
        rows, intake = encode_trace(trace, data["rgb"], history=4, grid=8)
    dispatch = next(r for r in rows if r["command_id"] == first_command)
    # Same observation and completed history as the first actual macro dispatch,
    # evaluated at the earlier, explicitly recorded decision instant.
    dispatch["as_of"] = decision["decision_at"]
    features = recovery_features(dispatch, proposal)
    features["decision_id"] = decision["decision_id"]
    features["continuation_context_reference"] = decision["continuation_context_reference"]
    report = {"schema": "full-fold-recovery-chain-audit/1", "trial_id": record["trial_id"],
              "decision_id": decision["decision_id"], "candidate_id": proposal["candidate_id"],
              "rgb_frames": intake["rgb_frames"], "observations": intake["observations"],
              "actual_dispatches_with_feedback": intake["dispatch_inputs"],
              "macro_dispatches": macro_dispatches, "macro_feature_dimensions": len(features["candidate_target"]),
              "proposal_persisted_before_decision": True,
              "same_trial_continuous_chain": True, "upstream_diagnostic_outcome": final,
              "source_manifest_sha256": digest(root / "manifest.json"),
              "continuation_success": None, "label_review_reference": None,
              "training_ready": False, "independent_review_status": "pending",
              "maximum_rgb_gap_sim_s": float(np.diff(sorted({o["rendering_time_s"] for o in trace["observations"]})).max())}
    if output is not None:
        output = Path(output).resolve()
        require(output != root and root not in output.parents and not output.exists(),
                "export must be a new directory outside evidence")
        output.mkdir(parents=True)
        pending = {"schema": "recovery-chain-pending-review/1", **decision, "features": features}
        pending["schema"] = "recovery-chain-pending-review/1"
        (output / "pending-review.json").write_text(json.dumps(pending, indent=2, allow_nan=False), encoding="utf-8")
        (output / "audit.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trial_directory", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.trial_directory, args.output), indent=2))
