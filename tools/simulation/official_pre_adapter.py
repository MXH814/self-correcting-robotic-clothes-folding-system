"""Real detector/workflow adapter; no simulator is imported and no permit is invented.

The C runner uses ``observe`` only. A/B integration may call ``execute_macro``
after its external coordinator supplies four fresh evidence records and, after
waiting for rest, ``refresh_preflight`` reconfirms the alert on a new RGB frame.
Each evidence record needs ``passed``, ``reference``, and ``measured_wall_s``.
Missing evidence rejects before any SDK call. Geometry verification remains a
separate fresh-observation step; the returned continuation request is not motion
authorization. Software fixture tests are not measured robot permissions.
"""
import hashlib
import json
import math
from pathlib import Path
import time

import numpy as np

from pre_detection_bridge import create_runtime, make_input, DiagnosticRecoveryWorkflow, JsonlJournal

PERMIT_FIELDS = ("authority", "measured_rest", "queue_empty", "macro_validated")


class OfficialPreAdapter:
    def __init__(self, trace, *, package_dir, encoder_weights, context_reference,
                 journal_path, device="cpu"):
        self.trace = trace
        self.runtime = create_runtime(package_dir=package_dir, encoder_weights=encoder_weights,
                                      context_reference=context_reference, device=device)
        package_id = self.runtime.detector.meta["package_id"] if self.runtime.detector is not None else None
        self.flow = DiagnosticRecoveryWorkflow(
            trace.trial_id, journal=JsonlJournal(journal_path),
            detector_package_id=package_id, context_reference=context_reference)

    def observe(self, observation, *, controller_phase, expected_holding):
        metadata = make_input(self.trace, observation, controller_phase=controller_phase,
                              runtime=self.runtime)
        captured = observation["camera_read_begin"]["wall_monotonic_ns"] / 1e9
        report = self.runtime.observe(
            self.trace.frames[observation["frame_index"]], metadata,
            generation=self.flow.generation, captured_wall_s=captured,
            now_wall_s=time.monotonic())
        request = self.flow.on_detection(report, now_wall_s=time.monotonic(),
                                         expected_holding=expected_holding)
        return metadata, report, request

    def refresh_preflight(self, observation, *, controller_phase="HOLD"):
        """Read a new RGB frame after rest/preflight work without extending old clocks.

        Returns metadata, runtime report and a workflow event. Only
        PREFLIGHT_DETECTION_REFRESHED retains the pending request for execution.
        All other outcomes require the caller to keep dispatch disabled.
        """
        if self.flow.state != "RECOVERY_REQUESTED":
            raise ValueError("Only a pending recovery request can refresh preflight detection")
        if controller_phase not in ("HOLD", "LIFT", "LEFT_SLEEVE_HOLD", "RIGHT_SLEEVE_HOLD"):
            raise ValueError("Preflight refresh requires expected holding")
        metadata = make_input(self.trace, observation, controller_phase=controller_phase,
                              runtime=self.runtime)
        report = self.runtime.observe(
            self.trace.frames[observation["frame_index"]], metadata,
            generation=self.flow.generation,
            captured_wall_s=observation["camera_read_begin"]["wall_monotonic_ns"] / 1e9,
            now_wall_s=time.monotonic())
        event = self.flow.refresh_preflight_detection(self.flow.request_id, report,
                                                      now_wall_s=time.monotonic())
        return metadata, report, event

    def _proposal_binding(self, chain, proposal):
        """Bind the entire supplied proposal, not just its reusable candidate ID."""
        binding = {"schema": "pre-macro-proposal-binding/1", "passed": False,
                   "proposal_sha256": None, "reason": "INVALID_PROPOSAL_BINDING"}
        try:
            decision = chain.decision
            if not (isinstance(proposal, dict) and isinstance(decision, dict)
                    and chain.trial_id == self.flow.trial_id
                    and decision.get("trial_id") == self.flow.trial_id
                    and proposal.get("trial_id") == self.flow.trial_id
                    and proposal.get("candidate_id") == decision.get("candidate_id")):
                return binding
            path = Path(chain.output) / "macro-proposal.json"
            content = path.read_bytes()
            digest = hashlib.sha256(content).hexdigest()
            binding.update(proposal_sha256=digest, reference=str(path))
            expected = "macro-proposal.json#sha256=" + digest
            if decision.get("candidate_spec_reference") != expected:
                binding["reason"] = "PROPOSAL_FILE_HASH_MISMATCH"
                return binding
            stored = json.loads(content)
            # JSON equality also rejects booleans substituted for numeric fields,
            # NaN, unknown/non-JSON objects and extra/missing proposal fields.
            canonical = lambda value: json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":"))
            if canonical(stored) != canonical(proposal):
                binding["reason"] = "PROPOSAL_CONTENT_MISMATCH"
                return binding
            binding.update(passed=True, reason="PERSISTED_PROPOSAL_MATCH")
        except (OSError, ValueError, TypeError, AttributeError) as error:
            binding["detail"] = str(error)
        return binding

    def execute_macro(self, request, *, chain, proposal, robot, original_move,
                      preflight_evidence=None):
        """Connect the official acceptance gate to the existing real five-operation macro.

        The caller must persist a proposal via ``chain.propose`` first and supply
        actual current-generation coordinator/rest/queue/path evidence. This
        adapter cannot measure authority or legal motion limits itself. Empty,
        stale or unreferenced evidence is a negative permit, never a fallback.
        ``original_move`` is the saved original SDK method, avoiding recursion.
        """
        if request.get("kind") != "REQUEST_RECOVERY_PREFLIGHT":
            raise ValueError("Only an official recovery preflight request can reach the macro")
        binding = self._proposal_binding(chain, proposal)
        now = time.monotonic()
        evidence = preflight_evidence if isinstance(preflight_evidence, dict) else {}
        permit = {"trial_id": evidence.get("trial_id"), "generation": evidence.get("generation"),
                  "now_wall_s": now}
        # Missing evidence is assigned the current identity only to record the
        # explicit four-negative refusal instead of inventing a measured result.
        if not evidence:
            permit.update(trial_id=self.flow.trial_id, generation=self.flow.generation)
        for name in PERMIT_FIELDS:
            item = evidence.get(name, {})
            measured = item.get("measured_wall_s") if isinstance(item, dict) else None
            permit[name] = bool(isinstance(item, dict) and item.get("passed") is True
                                and isinstance(item.get("reference"), str) and item["reference"].strip()
                                and type(measured) in (float, int) and math.isfinite(measured)
                                and 0 <= now - measured <= 1)
        permit["macro_validated"] = permit["macro_validated"] and binding["passed"]
        # Persist the evidence consumed by begin_macro, before any dispatch.
        self.flow.journal({"schema": "pre-external-preflight-evidence/1", "trial_id": self.flow.trial_id,
                           "generation": self.flow.generation, "request_id": request.get("request_id"),
                           "evidence": evidence, "permit": dict(permit),
                           "proposal_binding": binding, "motion_authorized": False})
        # Journal fsync and hashing take real time; they cannot extend evidence
        # validity. Recheck at the actual acceptance call, without issuing motion.
        permit["now_wall_s"] = time.monotonic()
        for name in PERMIT_FIELDS:
            if permit[name]:
                measured = evidence[name]["measured_wall_s"]
                permit[name] = 0 <= permit["now_wall_s"] - measured <= 1
        accepted = self.flow.begin_macro(request.get("request_id"), permit=permit)
        if accepted["kind"] != "MACRO_ACCEPTED":
            return accepted
        completed = []
        orientation = np.asarray(proposal["orientation_wxyz"])

        def step(name, function, **kwargs):
            chain.operation(name, function, **kwargs)
            completed.append(name)

        def move(key):
            return original_move(np.asarray(proposal[key]), orientation,
                                 angular_type="quat", dense_sample_scale=0.01)

        def requested(key):
            return {"target_world_m": proposal[key], "orientation_wxyz": proposal["orientation_wxyz"],
                    "dense_sample_scale_m": 0.01}

        try:
            step("release", lambda: robot.set_both_hand_state(left_hand_state="open"),
                 wait_steps=proposal["open_wait_steps"], requested={"hand_state": "open"})
            step("retreat", lambda: move("retreat_world_m"), fail_on_false=True,
                 requested=requested("retreat_world_m"))
            step("regrasp", lambda: move("pick_world_m"), fail_on_false=True,
                 requested=requested("pick_world_m"))
            step("close", lambda: robot.set_both_hand_state(left_hand_state="close"),
                 wait_steps=proposal["close_wait_steps"], requested={"hand_state": "close"})
            step("lift", lambda: move("lift_world_m"), fail_on_false=True,
                 requested=requested("lift_world_m"))
            # Advance only physics for the final dispatch feedback; no new command.
            chain.env.step()
            chain.trace.observe("VERIFY_RECOVERY", force=True)
            feedback_complete = not chain.trace.pending_feedback
        except BaseException:
            self.flow.finish_macro(request["request_id"], operations=completed, feedback_complete=False,
                                   finish_sim_s=chain.trace.clock()["sim_time_s"])
            raise
        return self.flow.finish_macro(request["request_id"], operations=completed,
                                      feedback_complete=feedback_complete,
                                      finish_sim_s=chain.trace.clock()["sim_time_s"])
