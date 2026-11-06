"""Pure offline preflight checker. NOT a coordinator, trajectory checker or stop certificate."""
from dataclasses import dataclass
from typing import Tuple
from .diagnostics import finite


@dataclass(frozen=True)
class Context:
    generation: int
    now_s: float
    observation_s: float
    inference_started_s: float
    attempts: int
    active_sim_s: float
    cost: float
    cost_cap: float
    authority: bool
    stop_pending: bool
    profile_version: str
    continuation_version: str
    policy_version: str
    calibration_ref: str
    channels: Tuple[str, ...]
    lower: Tuple[float, ...]
    upper: Tuple[float, ...]
    max_prefix_s: float


def select_candidate(decision, ctx):
    """Returns candidate ID/reason only. Caller must recheck atomically at dispatch.

    Numeric limits are endpoint limits; full trajectory validity remains an adapter task.
    Calibration reference equality assumes an independently approved trusted context.
    """
    times = (ctx.now_s, ctx.observation_s, ctx.inference_started_s, ctx.active_sim_s,
             ctx.cost, ctx.cost_cap, ctx.max_prefix_s)
    if not all(finite(x) for x in times) or ctx.cost < 0 or ctx.cost_cap <= 0 or ctx.active_sim_s < 0:
        return None, "INVALID_CONTEXT"
    if type(ctx.attempts) is not int or ctx.attempts < 0:
        return None, "INVALID_CONTEXT"
    if not ctx.authority:
        return None, "AUTHORITY_REVOKED"
    if ctx.stop_pending:
        return None, "STOP_PENDING"
    if decision.get("control_generation") != ctx.generation:
        return None, "OLD_GENERATION"
    if not 0 <= ctx.now_s - ctx.observation_s <= 1:
        return None, "STALE_OBSERVATION"
    if not 0 <= ctx.inference_started_s - ctx.observation_s <= 1:
        return None, "STALE_AT_INFERENCE"
    if not 0 <= ctx.now_s - ctx.inference_started_s < 2:
        return None, "DECISION_TIMEOUT"
    if ctx.attempts >= 3 or ctx.active_sim_s >= 300 or ctx.cost >= ctx.cost_cap:
        return None, "BUDGET_EXHAUSTED"
    if decision.get("profile_version") != ctx.profile_version:
        return None, "PROFILE_MISMATCH"
    candidates = decision.get("candidates")
    if not isinstance(candidates, list):
        return None, "INVALID_SCHEMA"
    if len(candidates) > 8:
        return None, "TOO_MANY_CANDIDATES"
    if not (len(ctx.channels) == len(ctx.lower) == len(ctx.upper) > 0
            and len(set(ctx.channels)) == len(ctx.channels)
            and all(finite(lo) and finite(hi) and lo <= hi for lo, hi in zip(ctx.lower, ctx.upper))
            and ctx.max_prefix_s > 0 and ctx.calibration_ref):
        return None, "INVALID_PROFILE"
    ids = [c.get("candidate_id") for c in candidates if isinstance(c, dict)]
    if len(ids) != len(candidates) or any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
        return None, "INVALID_SCHEMA"
    accepted = []
    for c in candidates:
        values = c.get("values")
        if (c.get("channels") != list(ctx.channels) or not isinstance(values, list)
                or len(values) != len(ctx.channels) or not all(finite(x) for x in values)):
            continue
        if not all(lo <= x <= hi for x, lo, hi in zip(values, ctx.lower, ctx.upper)):
            continue
        duration = c.get("prefix_duration_sim_s")
        if not finite(duration) or not 0 < duration <= min(ctx.max_prefix_s, 300 - ctx.active_sim_s):
            continue
        if (c.get("score_semantics") != "conditional_full_task_success"
                or c.get("calibration_ref") != ctx.calibration_ref
                or c.get("continuation_version") != ctx.continuation_version
                or c.get("policy_version") != ctx.policy_version):
            continue
        score = c.get("score")
        if finite(score) and .6 <= score <= 1:
            accepted.append(c)
    if not accepted:
        return None, "NO_QUALIFIED_CANDIDATE"
    chosen = min(accepted, key=lambda c: (-c["score"], c["candidate_id"]))
    return chosen["candidate_id"], "PREFLIGHT_ONLY"
