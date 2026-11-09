"""Ma/Hu detector -> existing macro -> fresh post-check bridge for Pre integration.

No detector, visual encoder, thresholds or geometry rules are implemented here.
All callbacks must be connected explicitly; missing components fail closed.
"""
import math


def execute_existing_macro(chain, robot, move, pick, lift, orientation):
    """Bind the existing five-operation executor, preserving proposal-before-dispatch."""
    import numpy as np
    proposal = chain.propose(pick, lift, orientation)
    chain.operation("release", lambda: robot.set_both_hand_state(left_hand_state="open"),
                    wait_steps=proposal["open_wait_steps"], requested={"hand_state": "open"})
    for name, key in (("retreat", "retreat_world_m"), ("regrasp", "pick_world_m"),
                      ("close", None), ("lift", "lift_world_m")):
        if name == "close":
            chain.operation("close", lambda: robot.set_both_hand_state(left_hand_state="close"),
                            wait_steps=proposal["close_wait_steps"], requested={"hand_state": "close"})
        else:
            chain.operation(name, lambda k=key: move(np.asarray(proposal[k]),
                np.asarray(proposal["orientation_wxyz"]), angular_type="quat", dense_sample_scale=.01),
                fail_on_false=True, requested={"target_world_m": proposal[key],
                    "orientation_wxyz": proposal["orientation_wxyz"], "dense_sample_scale_m": .01})
    return {"completed": True, "candidate_id": proposal["candidate_id"],
            "operations": ["release", "retreat", "regrasp", "close", "lift"],
            "end_clock": chain.trace.clock(),
            "evidence_reference": "full-fold-recovery.json#macro_execution"}


def observe_live(chain):
    obs = chain.trace.observe(chain.phase, force=True)
    return {"trial_id": chain.trial_id, "observation_id": obs["observation_id"],
            "rgb": chain.trace.frames[obs["frame_index"]], "frame_index": obs["frame_index"],
            "rendering_time_s": obs["rendering_time_s"], "capture_clock": obs["joint_read_end"],
            "phase": obs["phase"], "joint_state": obs["joint_state"],
            "camera_reference": chain.context["camera"]}


def bind_existing_runtime(chain, robot, original_move, pick, lift, orientation, *,
                          detect=None, check_after=None, emit=lambda event: None):
    def fresh():
        chain.phase = "recovery-check"
        # Advance the simulator/render so the postcheck cannot reuse a pre-macro image.
        for _ in range(3):
            chain.env.step()
        return observe_live(chain)
    return PreRuntimeBridge(detect=detect, check_after=check_after, emit=emit,
        execute_macro=lambda obs, report: execute_existing_macro(chain, robot, original_move,
                                                                 pick, lift, orientation),
        observe_after=fresh)


class PreRuntimeBridge:
    def __init__(self, *, detect=None, execute_macro=None, observe_after=None,
                 check_after=None, emit=lambda event: None, attempts=1):
        self.detect, self.execute_macro = detect, execute_macro
        self.observe_after, self.check_after = observe_after, check_after
        self.emit, self.remaining = emit, attempts
        self.handled = set()
        self.locked = False

    def event(self, kind, **fields):
        event = {"schema": "pre-control-event/1", "kind": kind, **fields}
        self.emit(event)
        return event

    def help(self, reason):
        self.locked = True
        self.event("HELP_REQUESTED", reason=reason, automatic_dispatch_enabled=False,
                   physical_rest_confirmed=False, manual_authority_granted=False)
        return "HELP_NO_NEW_DISPATCH"

    def report(self, callback, obs, kind):
        if callback is None:
            value = {"status": "UNKNOWN", "reason": "DETECTOR_OR_POSTCHECK_NOT_LOADED",
                     "observation_id": obs["observation_id"], "trial_id": obs["trial_id"],
                     "score": None, "threshold": None, "method": None}
        else:
            # Explicit allowlist: neither injection metadata nor final outcome enters inference.
            packet = {key: obs[key] for key in ("trial_id", "observation_id", "rgb", "capture_clock", "rendering_time_s", "frame_index",
                       "phase", "joint_state", "camera_reference") if key in obs}
            value = callback(packet)
            if (value.get("observation_id") != obs["observation_id"]
                    or value.get("trial_id") != obs["trial_id"]):
                raise ValueError("Detector result is for another observation/trial")
            if value.get("status") not in ("NORMAL", "ANOMALY", "UNKNOWN"):
                raise ValueError("Unsupported detector state")
            if value["status"] != "UNKNOWN":
                for key in ("method", "model_ref", "threshold_ref", "preprocessing_ref"):
                    if not value.get(key):
                        raise ValueError("Missing detector provenance: " + key)
                if not all(isinstance(value.get(k), (int, float)) and math.isfinite(value[k])
                           for k in ("score", "threshold")):
                    raise ValueError("Missing/nonfinite score or threshold")
        self.event(kind, report=value)
        return value

    def handle(self, obs, *, expected_hold, action_inflight=False, authorized=True):
        if self.locked or not authorized:
            return self.help("DISPATCH_LOCKED_OR_UNAUTHORIZED")
        key = (obs["trial_id"], obs["observation_id"])
        if key in self.handled:
            return "DUPLICATE_NO_DISPATCH"
        if action_inflight:
            return "WAIT_FOR_ACTION_COMPLETION"
        if not expected_hold:
            self.event("RULE_NOT_APPLICABLE", observation_id=obs["observation_id"], reason="PLANNED_RELEASE_OR_OTHER_PHASE")
            return "CONTINUE_PLANNED_RELEASE"
        self.handled.add(key)
        try:
            report = self.report(self.detect, obs, "DETECTION")
            if report["status"] == "UNKNOWN":
                return self.help(report.get("reason", "UNKNOWN"))
            if report["status"] == "NORMAL":
                self.event("CONTINUE", reason="DETECTOR_NORMAL")
                return "CONTINUE"
            if self.remaining <= 0:
                return self.help("RECOVERY_BUDGET_EXHAUSTED")
            if None in (self.execute_macro, self.observe_after, self.check_after):
                return self.help("RECOVERY_OR_POSTCHECK_NOT_BOUND")
            self.remaining -= 1
            self.event("RECOVERY_REQUEST", observation_id=obs["observation_id"], trigger=report,
                       attempts_remaining=self.remaining)
            executed = self.execute_macro(obs, report)
            self.event("RECOVERY_EXECUTION", evidence=executed)
            if not executed.get("completed"):
                return self.help("RECOVERY_EXECUTION_FAILED")
            fresh = self.observe_after()
            end_clock = executed.get("end_clock", obs["capture_clock"])
            if (fresh["trial_id"] != obs["trial_id"] or fresh["observation_id"] == obs["observation_id"]
                    or fresh["capture_clock"]["sim_time_s"] <= obs["capture_clock"]["sim_time_s"]
                    or fresh["capture_clock"]["wall_monotonic_ns"] <= obs["capture_clock"]["wall_monotonic_ns"]
                    or fresh["capture_clock"]["sim_time_s"] < end_clock["sim_time_s"]
                    or fresh["capture_clock"]["wall_monotonic_ns"] < end_clock["wall_monotonic_ns"]
                    or fresh.get("rendering_time_s", end_clock["sim_time_s"]) < end_clock["sim_time_s"]):
                return self.help("POSTCHECK_OBSERVATION_NOT_FRESH")
            checked = self.report(self.check_after, fresh, "RECOVERY_CHECK")
            if checked["status"] != "NORMAL":
                return self.help("RECOVERY_CHECK_" + checked["status"])
            self.event("CONTINUE", reason="POSTCHECK_NORMAL")
            return "CONTINUE_AFTER_RECOVERY"
        except Exception as error:
            return self.help("ADAPTER_ERROR: " + str(error))
