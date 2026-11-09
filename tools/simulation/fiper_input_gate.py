"""Validate RND-OE adaptation inputs; no policy or action samples are required."""

FIPER_COMMIT = "13d79c5c3069def843e454787ff128defc249838"


def check_fiper_inputs(packet):
    missing = [key for key in ("encoder_ref", "preprocessing_ref", "obs_embeddings",
                              "rnd_checkpoint_ref", "calibration_ref") if packet.get(key) is None]
    result = {"status": "UNKNOWN", "reason": "FIPER_INPUTS_UNAVAILABLE", "missing": missing,
              "observation_id": packet["observation_id"], "observation_clock": packet["observation_clock"],
              "method": "FIPER-RND-OE-observation-adaptation", "official_commit": FIPER_COMMIT, "scores_computed": False,
              "recovery_authorized": False}
    if missing:
        return result
    import numpy as np
    embeddings = np.asarray(packet["obs_embeddings"])
    if embeddings.size == 0 or not np.isfinite(embeddings).all():
        return {**result, "reason": "INVALID_FIPER_TENSORS"}
    # Encoder, RND weights and calibration compatibility need Ma/Hu's actual backend.
    return {**result, "reason": "OFFICIAL_BACKEND_AND_CALIBRATION_NOT_BOUND"}


def recovery_gate(report, *, expected_hold, attempts_remaining, action_inflight):
    """Only an authenticated, calibrated detector result can authorize a later macro."""
    if not expected_hold:
        return "CONTINUE_PLANNED_RELEASE"
    if action_inflight:
        return "WAIT_FOR_ACTION_COMPLETION"
    if (not report.get("scores_computed") or not report.get("calibration_verified")
            or report.get("status") == "UNKNOWN"):
        return "HELP_NO_NEW_DISPATCH"
    if report["status"] == "NORMAL":
        return "CONTINUE"
    if report["status"] == "ANOMALY" and attempts_remaining > 0:
        return "REQUEST_RECOVERY"
    return "HELP_NO_NEW_DISPATCH"
