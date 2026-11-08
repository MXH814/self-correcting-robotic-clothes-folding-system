"""Build traceable development-proxy macro samples without changing raw labels."""
import argparse
import copy
import json
from pathlib import Path
import sys
import tempfile

from .diagnostics import require
from .runtime_intake import digest
from .shared_context import ENCODING_REFERENCE, PROXY_TARGET, canonical_bytes, content_hash, freeze_context, shared_reference


def region_result(points, bounds, threshold):
    import numpy as np
    require(isinstance(points,np.ndarray) and points.ndim==2 and points.shape[1]==3
            and len(points)>0 and bool(np.isfinite(points).all()), "invalid proxy point cloud")
    require(isinstance(bounds,list) and len(bounds)==4 and all(type(x) in (int,float) and np.isfinite(x) for x in bounds),
            "invalid proxy boundary")
    x0,x1,y0,y1=bounds
    require(x0<x1 and y0<y1 and type(threshold) in (int,float) and np.isfinite(threshold)
            and 0<threshold<=1, "invalid region/threshold")
    count=int(((points[:,0]>=x0)&(points[:,0]<=x1)&(points[:,1]>=y0)&(points[:,1]<=y1)).sum())
    return dict(inside_count=count,point_count=len(points),ratio=count/len(points),passed=count/len(points)>=threshold)


def readiness(rows):
    from .sequence_ranker import validate_training_rows
    train, dev = validate_training_rows(rows, require_coverage=False, allow_unassigned=True)
    blockers = []
    if {r["continuation_success"] for r in train} != {False, True}:
        blockers.append("training partition lacks both verified positive and negative proxy outcomes")
    if not dev:
        blockers.append("no separate development partition with verified outcomes")
    if any(r["split"] == "unassigned" for r in rows):
        blockers.append("unassigned lineage groups require a frozen partition manifest")
    return {"curated_macro_samples": len(rows), "positive_proxy_samples": sum(r["continuation_success"] for r in rows),
            "negative_proxy_samples": sum(not r["continuation_success"] for r in rows),
            "training_samples": len(train), "development_samples": len(dev), "blockers": blockers,
            "software_training_admission_ready": not blockers,
            "research_sufficiency_established": False, "online_authorized": False}


def build(root, output, split="unassigned", expected_context=None):
    import numpy as np
    root, output = Path(root).resolve(), Path(output).resolve()
    require(split in ("unassigned", "train", "development"), "invalid split")
    require(root != output and root not in output.parents and not output.exists(), "new output outside evidence required")
    tools = Path(__file__).resolve().parents[1] / "tools" / "simulation"
    sys.path.insert(0, str(tools))
    try:
        from verify_fold_recovery_chain import audit
    finally:
        sys.path.remove(str(tools))
    with tempfile.TemporaryDirectory(prefix="macro-intake-") as temporary:
        pending_dir = Path(temporary) / "pending"
        chain_audit = audit(root, pending_dir)
        pending = json.loads((pending_dir / "pending-review.json").read_text(encoding="utf-8"))
    record = json.loads((root / "full-fold-recovery.json").read_text(encoding="utf-8"))
    context = json.loads((root / "continuation-context.json").read_text(encoding="utf-8"))
    require(context["trial_id"] == pending["trial_id"] == record["trial_id"], "cross-trial data compilation")
    shared = freeze_context(context, pending["features"]["profile_id"], record["garment"])
    if expected_context is not None:
        expected=json.loads(Path(expected_context).read_text(encoding="utf-8"))
        changed=[key for key in sorted(set(expected)|set(shared)) if expected.get(key)!=shared.get(key)]
        require(not changed, "frozen shared context mismatch: " + ", ".join(changed))
    # This first protocol is explicitly the recorded upstream 88% region proxy.
    require(shared["target"]["minimum_ratio"] == .88, "this protocol freezes the 88% development proxy")
    judgment = record["judgment"]
    bounds=judgment['boundary_world_xy_m']
    with np.load(root/'final-point-cloud.npz',allow_pickle=False) as data:
        final_result=region_result(data['points'],bounds,.88)
    with np.load(root/'initial-point-cloud.npz',allow_pickle=False) as data:
        initial_result=region_result(data['points'],bounds,.88)
    require(final_result['inside_count']==judgment['inside_count'] and final_result['point_count']==judgment['point_count']
            and final_result['passed']==judgment['upstream_success'], 'proxy recount differs from raw result')
    proxy = final_result['passed']
    review = {"schema": "deterministic-proxy-review/1", "trial_id": pending["trial_id"],
              "target_id": PROXY_TARGET, "continuation_success_for_this_proxy": proxy,
              "inside_count": judgment["inside_count"], "point_count": judgment["point_count"],
              "threshold": .88, "method": "deterministic point-cloud recount through validated chain intake",
              "scope": "development proxy; not DR02, local recovery, SRS quality or autonomous success",
              "human_annotation_claimed": False, "independent_team_review_status": "pending",
              "source_manifest_sha256": chain_audit["source_manifest_sha256"],
              "source_final_point_cloud_sha256": digest(root / "final-point-cloud.npz"),
              "source_full_fold_record_sha256": digest(root / "full-fold-recovery.json"),
              "raw_continuation_success": pending["continuation_success"], "raw_labels_modified": False}
    review['final_region_recount']=final_result
    review['initial_state_control']=initial_result
    review['initial_state_is_recovery_training_negative']=False
    features = copy.deepcopy(pending["features"])
    features["source_context_reference"] = pending["continuation_context_reference"]
    features["continuation_context_reference"] = shared_reference(shared)
    features["encoding_reference"] = ENCODING_REFERENCE
    row = {"schema": "reviewed-recovery-sample/1", "decision_scope": "recovery_macro",
           "trial_id": pending["trial_id"], "lineage_group": pending["lineage_group"],
           "decision_id": pending["decision_id"], "candidate_id": pending["candidate_id"], "split": split,
           "target_definition": "fixed-controller-continuation/v1", "supervision_target_id": PROXY_TARGET,
           "continuation_context_reference": shared_reference(shared),
           "source_context_reference": pending["continuation_context_reference"],
           "candidate_spec_reference": pending["candidate_spec_reference"],
           "candidate_available_before_decision": pending["candidate_available_before_decision"],
           "encoding_reference": ENCODING_REFERENCE, "continuation_success": proxy,
           "label_review_reference": "proxy-review.json#sha256=" + content_hash(review),
           "label_provenance": "deterministic named development proxy; no human label impersonation",
           "source_manifest_sha256": chain_audit["source_manifest_sha256"], "features": features}
    row['purpose']='development_proxy';row['sealed_test_allowed']=False
    row['condition']=record['injection']
    row['method']='scripted_macro_exploration'
    status = readiness([row])
    output.mkdir(parents=True)
    for name, value in {"shared-context.json": shared, "proxy-review.json": review,
                        "readiness.json": status, "source-chain-audit.json": chain_audit}.items():
        (output / name).write_bytes(canonical_bytes(value))
    (output / "samples.jsonl").write_bytes(canonical_bytes(row))
    binding = {"schema": "recovery-proxy-dataset-export/1", "trial_id": pending["trial_id"],
               "shared_context_reference": shared_reference(shared),
               "source_context_reference": pending["continuation_context_reference"],
               "source_manifest_sha256": chain_audit["source_manifest_sha256"],
               "source_initial_point_cloud_sha256": context["target"]["initial_point_cloud_sha256"],
               "builder_sha256": digest(__file__),
               "expected_shared_context_checked": expected_context is not None,
               "files": {p.name: digest(p) for p in sorted(output.iterdir())}, "readiness": status}
    (output / "manifest.json").write_bytes(canonical_bytes(binding))
    return binding


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chain-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--split", choices=("unassigned", "train", "development"), default="unassigned")
    parser.add_argument("--expected-shared-context",help="Frozen shared-context JSON; reject camera/controller/target/encoding drift")
    args = parser.parse_args()
    print(json.dumps(build(args.chain_dir, args.output_dir, args.split,args.expected_shared_context), indent=2))


if __name__ == "__main__":
    main()
