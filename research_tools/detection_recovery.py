"""Diagnostic detection-to-macro workflow. Emits requests, never robot commands.

External coordinator/adapter must supply measured rest, empty-queue and legal
macro evidence. This is NOT replacement product authorization or SRS acceptance.
Geometry checks may use privileged simulation points only when declared.
"""
from collections import deque
import json
import math
import os
from pathlib import Path
import uuid

from .diagnostics import finite, require

OPERATIONS = ("release", "retreat", "regrasp", "close", "lift")


class JsonlJournal:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # One fresh journal per diagnostic trial; never reuse an existing file.
        self.path.open("x", encoding="utf-8").close()

    def __call__(self, event):
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())


class GeometryHoldMonitor:
    """Explicitly configured distance/height check; not formal OFFSET/SLIP labels."""
    def __init__(self, *, table_z_m, min_cloth_height_m, max_hand_distance_m,
                 window_s=.2, min_samples=3, max_gap_s=.25):
        require(all(finite(x) for x in (table_z_m, min_cloth_height_m, max_hand_distance_m,
                                      window_s, max_gap_s)) and min_cloth_height_m > 0
                and max_hand_distance_m > 0 and window_s > 0 and max_gap_s > 0
                and type(min_samples) is int and min_samples >= 2, "invalid geometric profile")
        self.table_z = table_z_m
        self.min_height = min_cloth_height_m
        self.max_distance = max_hand_distance_m
        self.window_s, self.min_samples, self.max_gap = window_s, min_samples, max_gap_s
        self.samples = deque()
        self.key = None
        self.last = None

    def reset(self):
        self.samples.clear()
        self.key, self.last = None, None

    def update(self, *, trial_id, generation, observation_id, frame_id, sim_time_s,
               hand_xyz_m, cloth_xyz_m, provenance, phase, captured_wall_s, now_wall_s):
        result = {"schema": "geometry-hold-report/1", "method": "task-conditioned-hold-geometry/1",
                  "trial_id": trial_id, "generation": generation, "observation_id": observation_id,
                  "frame_id": frame_id, "observed_sim_s": sim_time_s, "status": "UNKNOWN",
                  "reason": "INVALID_INPUT", "provenance": provenance,
                  "captured_wall_s": captured_wall_s, "decision_wall_s": now_wall_s,
                  "srs_quality": None, "dr02_label": None, "motion_authorized": False}
        try:
            require(provenance in ("visible_depth_material_patch", "privileged_sim_material_patch"), "UNDECLARED_GEOMETRY")
            require(phase in ("HOLD", "LIFT", "VERIFY_RECOVERY"), "UNSUPPORTED_PHASE")
            require(type(generation) is int and generation >= 0 and finite(sim_time_s) and sim_time_s >= 0,
                    "INVALID_TIME_OR_GENERATION")
            require(finite(captured_wall_s) and finite(now_wall_s)
                    and 0 <= now_wall_s - captured_wall_s <= 1, "MISSING_OR_STALE_CLOCK")
            require(all(isinstance(v, str) and v for v in (trial_id, observation_id, frame_id)), "INVALID_IDENTITY")
            require(all(isinstance(v, (list, tuple)) and len(v) == 3 and all(finite(x) for x in v)
                        for v in (hand_xyz_m, cloth_xyz_m)), "MISSING_GEOMETRY")
            key = trial_id, generation, phase, provenance
            if self.key != key:
                self.reset()
            if self.last is not None:
                require(sim_time_s > self.last[0] and frame_id != self.last[1], "DUPLICATE_OR_REORDERED_FRAME")
                if sim_time_s - self.last[0] > self.max_gap:
                    self.samples.clear()
            distance = math.dist(hand_xyz_m, cloth_xyz_m)
            height = cloth_xyz_m[2] - self.table_z
            require(finite(distance) and finite(height), "INVALID_GEOMETRY_MEASUREMENT")
            held = distance <= self.max_distance and height >= self.min_height
            self.key, self.last = key, (sim_time_s, frame_id)
            self.samples.append((sim_time_s, held))
            while len(self.samples) > 1 and self.samples[1][0] <= sim_time_s - self.window_s:
                self.samples.popleft()
            result.update(distance_m=distance, cloth_height_m=height,
                          window_start_sim_s=self.samples[0][0], sample_count=len(self.samples))
            if len(self.samples) < self.min_samples or self.samples[-1][0] - self.samples[0][0] < self.window_s - 1e-9:
                result["reason"] = "WINDOW_WARMUP"
            elif all(x[1] for x in self.samples):
                result.update(status="HELD", reason="SUSTAINED_HOLD_GEOMETRY")
            elif all(not x[1] for x in self.samples):
                result.update(status="LOST", reason="SUSTAINED_HOLD_GEOMETRY_VIOLATION")
            else:
                result["reason"] = "UNSTABLE_HOLD_GEOMETRY"
        except (ValueError, TypeError) as error:
            self.reset()
            result["reason"] = str(error)
        return result


class DiagnosticRecoveryWorkflow:
    def __init__(self, trial_id, *, generation=0, max_attempts=1, journal=None,
                 detector_package_id=None, context_reference=None):
        require(isinstance(trial_id, str) and trial_id and type(generation) is int and generation >= 0,
                "invalid trial/generation")
        require(type(max_attempts) is int and max_attempts > 0, "invalid recovery budget")
        self.trial_id, self.generation = trial_id, generation
        self.max_attempts, self.attempts = max_attempts, 0
        self.journal = journal
        self.detector_package_id, self.context_reference = detector_package_id, context_reference
        self.state, self.request_id = "RUNNING", None
        self.accepted_report = None
        self.macro_finish_sim_s = None
        self.last_verification = None
        self.seen = set()

    def _event(self, kind, reason, **payload):
        event = {"schema": "diagnostic-recovery-event/1", "trial_id": self.trial_id,
                 "generation": self.generation, "state": self.state, "kind": kind,
                 "reason": reason, "attempts": self.attempts, "request_id": self.request_id,
                 "motion_authorized": False, **payload}
        if self.journal is not None:
            self.journal(event)  # A journal failure must prevent the caller from executing.
        return event

    def _help(self, reason):
        self.state = "HELP_REQUIRED"
        return self._event("REQUEST_HALT_AND_HELP", reason)

    def _detection_report_error(self, report, now_wall_s):
        """Common score/provenance/clock checks for initial and refreshed alerts."""
        from .observation_detector import METHOD
        if not (report.get("schema") == "observation-deviation-report/1" and report.get("method") == METHOD
                and report.get("motion_authorized") is False and type(report.get("generation")) is int):
            return "INVALID_DETECTION_REPORT"
        decision = report.get("decision_wall_s")
        captured = report.get("captured_wall_s")
        if not (finite(now_wall_s) and finite(decision) and finite(captured)
                and 0 <= decision - captured <= 1 and 0 <= now_wall_s - decision <= 1
                and now_wall_s - captured <= 1):
            return "STALE_OR_INVALID_REPORT"
        status = report.get("status")
        if status in ("NORMAL", "ANOMALY"):
            if not self.detector_package_id or not self.context_reference:
                return "DETECTOR_PACKAGE_NOT_BOUND"
            if (report.get("package_id") != self.detector_package_id
                    or report.get("context_reference") != self.context_reference):
                return "DETECTOR_PACKAGE_OR_CONTEXT_MISMATCH"
            score, raw, threshold = report.get("score"), report.get("raw_score"), report.get("threshold")
            if not (all(finite(x) and x >= 0 for x in (score, raw, threshold))
                    and (score > threshold) == (status == "ANOMALY")):
                return "INCONSISTENT_DETECTION_SCORE"
        return None

    def on_detection(self, report, *, now_wall_s, expected_holding):
        if not isinstance(report, dict):
            return self._help("INVALID_DETECTION_REPORT")
        if report.get("trial_id") != self.trial_id or report.get("generation") != self.generation:
            return self._event("REJECT", "OLD_GENERATION_OR_OTHER_TRIAL")
        if self.state != "RUNNING":
            return self._event("REJECT", "NOT_RUNNING")
        observed = report.get("observation_id")
        if not isinstance(observed, str) or not observed:
            return self._help("MISSING_OBSERVATION")
        if observed in self.seen:
            return self._event("REJECT", "DUPLICATE_OBSERVATION")
        self.seen.add(observed)
        if expected_holding is not True:
            return self._event("NO_RECOVERY", "OUTSIDE_EXPECTED_HOLD")
        error = self._detection_report_error(report, now_wall_s)
        if error:
            return self._help(error)
        status = report.get("status")
        if status == "NORMAL":
            return self._event("CONTINUE", "NORMAL_REFERENCE")
        if status == "UNKNOWN" and report.get("reason") == "WINDOW_WARMUP":
            return self._event("WAIT_FOR_OBSERVATION", "WINDOW_WARMUP")
        if status != "ANOMALY":
            return self._help("DETECTION_UNAVAILABLE_OR_UNKNOWN")
        if self.attempts >= self.max_attempts:
            return self._help("RECOVERY_BUDGET_EXHAUSTED")
        self.state, self.request_id = "RECOVERY_REQUESTED", str(uuid.uuid4())
        self.accepted_report = dict(report)
        return self._event("REQUEST_RECOVERY_PREFLIGHT", "OBSERVATION_ALERT",
                           source_observation_id=observed, detector_reason=report.get("reason"))

    def refresh_preflight_detection(self, request_id, report, *, now_wall_s):
        """Revalidate a pending request using a strictly newer, still-anomalous report.

        Waiting for measured rest is not permission to extend an old report's
        clock. A new report must pass the same provenance/score checks. A failed
        refresh makes the old report unusable; this never resets the budget or
        creates a new request/generation. No motion is authorized here.
        """
        if self.state != "RECOVERY_REQUESTED" or request_id != self.request_id:
            return self._event("REJECT", "INVALID_OR_DUPLICATE_REQUEST")
        if not isinstance(report, dict):
            return self._help("INVALID_DETECTION_REPORT")
        if report.get("trial_id") != self.trial_id or report.get("generation") != self.generation:
            return self._help("OLD_GENERATION_OR_OTHER_TRIAL")
        observed = report.get("observation_id")
        if not isinstance(observed, str) or not observed:
            return self._help("MISSING_OBSERVATION")
        if observed in self.seen:
            return self._help("DUPLICATE_OBSERVATION")
        self.seen.add(observed)
        error = self._detection_report_error(report, now_wall_s)
        if error:
            return self._help(error)
        if report.get("status") != "ANOMALY":
            return self._help("PREFLIGHT_ANOMALY_NOT_RECONFIRMED")
        previous = self.accepted_report
        if (not isinstance(previous, dict)
                or report["captured_wall_s"] <= previous["captured_wall_s"]):
            return self._help("PREFLIGHT_OBSERVATION_NOT_NEWER")
        # Actual runtime reports have observed_sim_s. Reject reused render times
        # even when a caller rereads an old frame under a fresh wall clock.
        observed_sim = report.get("observed_sim_s")
        previous_sim = previous.get("observed_sim_s")
        if (not finite(observed_sim) or observed_sim < 0
                or (finite(previous_sim) and observed_sim <= previous_sim)):
            return self._help("PREFLIGHT_FRAME_NOT_NEWER")
        if self.journal is None:
            return self._help("PERSISTENT_JOURNAL_REQUIRED")
        event = self._event("PREFLIGHT_DETECTION_REFRESHED", "FRESH_OBSERVATION_ALERT",
                            source_observation_id=observed,
                            previous_observation_id=previous["observation_id"], report=report)
        # A failed journal write must leave the old report in place, not refresh it.
        self.accepted_report = dict(report)
        return event

    def begin_macro(self, request_id, *, permit):
        if self.state != "RECOVERY_REQUESTED" or request_id != self.request_id:
            return self._event("REJECT", "INVALID_OR_DUPLICATE_REQUEST")
        if not isinstance(permit, dict):
            return self._help("INVALID_PREFLIGHT_PERMIT")
        if permit.get("trial_id") != self.trial_id or permit.get("generation") != self.generation:
            return self._event("REJECT", "OLD_GENERATION_OR_OTHER_TRIAL")
        if any(permit.get(k) is not True for k in ("authority", "measured_rest", "queue_empty", "macro_validated")):
            return self._help("PREFLIGHT_OR_REST_UNCONFIRMED")
        now = permit.get("now_wall_s")
        captured = self.accepted_report["captured_wall_s"]
        if not finite(now) or not 0 <= now - captured <= 1:
            return self._help("PREFLIGHT_REPORT_EXPIRED")
        if self.journal is None:
            return self._help("PERSISTENT_JOURNAL_REQUIRED")
        # Persist the acceptance BEFORE returning an execution request.
        event = self._event("MACRO_ACCEPTED", "EXTERNAL_PREFLIGHT_CONFIRMED",
                            operations=list(OPERATIONS), accepted_attempt_no=self.attempts + 1)
        self.attempts += 1
        self.state = "RECOVERING"
        return event

    def finish_macro(self, request_id, *, operations, feedback_complete, finish_sim_s):
        if self.state != "RECOVERING" or request_id != self.request_id:
            return self._event("REJECT", "INVALID_OR_DUPLICATE_FEEDBACK")
        if (not isinstance(operations, (list, tuple)) or tuple(operations) != OPERATIONS
                or feedback_complete is not True or not finite(finish_sim_s) or finish_sim_s < 0):
            return self._help("MACRO_FAILED_OR_FEEDBACK_INCOMPLETE")
        self.state, self.macro_finish_sim_s = "VERIFYING", finish_sim_s
        return self._event("REQUEST_NEW_HOLD_OBSERVATIONS", "MACRO_EXECUTION_IS_NOT_RECOVERY_SUCCESS")

    def verify(self, report, *, now_wall_s):
        if self.state != "VERIFYING":
            return self._event("REJECT", "NOT_VERIFYING")
        if not isinstance(report, dict):
            return self._help("INVALID_VERIFICATION_REPORT")
        if report.get("trial_id") != self.trial_id or report.get("generation") != self.generation:
            return self._event("REJECT", "OLD_GENERATION_OR_OTHER_TRIAL")
        if report.get("schema") != "geometry-hold-report/1" or report.get("motion_authorized") is not False:
            return self._help("INVALID_VERIFICATION_REPORT")
        captured = report.get("captured_wall_s")
        decision = report.get("decision_wall_s")
        if not (finite(captured) and finite(decision) and finite(now_wall_s)
                and 0 <= decision - captured <= 1 and 0 <= now_wall_s - decision <= 1
                and now_wall_s - captured <= 1):
            return self._help("VERIFICATION_STALE_OR_INVALID_CLOCK")
        t = report.get("observed_sim_s")
        frame = report.get("frame_id")
        if not finite(t) or t <= self.macro_finish_sim_s:
            return self._help("VERIFICATION_NOT_AFTER_MACRO")
        if self.last_verification and (t <= self.last_verification[0] or frame == self.last_verification[1]):
            return self._event("REJECT", "DUPLICATE_OR_REORDERED_VERIFICATION")
        self.last_verification = t, frame
        if report.get("status") == "HELD" and report.get("method") == "task-conditioned-hold-geometry/1":
            if not finite(report.get("window_start_sim_s")) or report["window_start_sim_s"] <= self.macro_finish_sim_s:
                return self._help("VERIFICATION_WINDOW_OVERLAPS_MACRO")
            self._event("RECOVERY_CHECK_PASSED", "LIMITED_HOLD_CHECK_ONLY", check=report)
            self.generation += 1
            self.state = "RUNNING"
            return self._event("REQUEST_FIXED_CONTINUATION", "NEW_GENERATION_AFTER_VERIFIED_HOLD")
        if report.get("status") == "UNKNOWN" and report.get("reason") == "WINDOW_WARMUP":
            return self._event("WAIT_FOR_OBSERVATION", "VERIFICATION_WINDOW_WARMUP")
        return self._help("RECOVERY_NOT_CONFIRMED")

    def revoke(self, reason="EXTERNAL_PAUSE_OR_TERMINATION"):
        self.generation += 1
        self.state = "HALT_REQUESTED"
        return self._event("REQUEST_HALT", reason)
