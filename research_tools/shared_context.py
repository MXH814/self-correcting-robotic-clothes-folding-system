"""Stable development context identity, separate from per-trial evidence hashes."""
import copy
import hashlib
import json
from pathlib import Path

from .diagnostics import finite, require

ENCODING_REFERENCE = "causal-rgb8-q-dq-history4-macro17/1"
PROXY_TARGET = "upstream-recorded-region-pass/1"


def canonical_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def content_hash(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def encoding_sources():
    root = Path(__file__).resolve().parent
    # Code identity is independent of checkout line endings; measured files are not normalized.
    return {name: hashlib.sha256((root/name).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            for name in ("garment_trace_intake.py", "legacy_features.py", "recovery_candidates.py")}


def freeze_context(context, profile_id, garment_id):
    require(context.get("schema") == "full-fold-continuation-context/1", "unsupported source context")
    require(context.get("target_definition") == "fixed-controller-continuation/v1", "unknown target definition")
    require(isinstance(context.get("trial_id"), str) and context["trial_id"], "missing source trial")
    require(isinstance(profile_id, str) and profile_id and isinstance(garment_id, str) and garment_id,
            "missing asset/profile identity")
    allowed = {"schema", "trial_id", "target_definition", "target", "controller", "camera", "preprocessing",
               "execution_profile", "budget", "human_policy", "context_status"}
    require(set(context) <= allowed, "new source context fields require explicit review")
    for key in ("target", "controller", "camera", "preprocessing", "execution_profile", "budget"):
        require(isinstance(context.get(key), dict) and bool(context[key]), "missing static context: " + key)
    target = copy.deepcopy(context["target"])
    initial = target.pop("initial_point_cloud_sha256", None)
    require(isinstance(initial, str) and len(initial) == 64, "missing per-trial initial geometry hash")
    ratio = target.get("minimum_ratio")
    require(finite(ratio) and 0 < ratio <= 1 and target.get("quality_is_srs_acceptance") is False,
            "development proxy cannot silently become SRS acceptance")
    require(target.get("boundary_source") and target.get("name"), "missing target rule")
    require(context["camera"].get("resolution_wh") and context["camera"].get("intrinsics_px"), "camera provenance")
    payload = {"schema": "shared-recovery-context/1", "garment_id": garment_id, "joint_profile_id": profile_id,
               "source_target_definition": context["target_definition"], "target": target,
               "supervision": {"target_id": PROXY_TARGET, "positive": "complete final point cloud passes recorded region rule",
                               "negative": "complete final point cloud fails recorded region rule",
                               "missing_or_aborted": "unknown, not an automatic negative",
                               "local_recovery_or_srs_autonomy": "not inferred"},
               "encoding_reference": ENCODING_REFERENCE, "encoding_sources_lf_sha256": encoding_sources(),
               "human_policy": context.get("human_policy"), "online_authorized": False}
    for key in ("controller", "camera", "preprocessing", "execution_profile", "budget"):
        payload[key] = copy.deepcopy(context[key])
    # trial_id, initial geometry hash and administrative status are preserved in each binding instead.
    canonical_bytes(payload)
    return payload


def shared_reference(shared):
    require(shared.get("schema") == "shared-recovery-context/1", "unsupported shared context")
    return "shared-context.json#sha256=" + content_hash(shared)
