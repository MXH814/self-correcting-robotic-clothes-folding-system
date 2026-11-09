"""Software fixtures only; not detector accuracy or measured robot permits."""
import hashlib
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/simulation"))
from official_pre_adapter import OfficialPreAdapter
from research_tools.observation_detector import METHOD
from research_tools.detection_recovery import DiagnosticRecoveryWorkflow


class OfficialAdapterTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        now = time.monotonic()
        self.obs = {"observation_id": "o1", "frame_index": 0, "rendering_frame": 1,
                    "rendering_time_s": 1., "camera_read_end": {"sim_time_s": 1.},
                    "camera_read_begin": {"wall_monotonic_ns": int(now * 1e9)},
                    "phase": "injection-must-not-leak"}
        self.trace = SimpleNamespace(trial_id="fixture", observations=[self.obs],
                                     frames=[np.zeros((4, 4, 3), dtype=np.uint8)])
        self.adapter = OfficialPreAdapter(self.trace, package_dir=Path(self.directory.name)/"absent",
            encoder_weights=Path(self.directory.name)/"absent.pth", context_reference="fixture-context",
            journal_path=Path(self.directory.name)/"journal.jsonl")

    def test_real_missing_runtime_requests_help(self):
        metadata, report, request = self.adapter.observe(self.obs, controller_phase="HOLD", expected_holding=True)
        self.assertEqual(report["status"], "UNKNOWN")
        self.assertEqual(request["kind"], "REQUEST_HALT_AND_HELP")
        self.assertEqual(metadata["phase"], "HOLD")
        self.assertNotIn("injection", metadata)
        self.assertIsNone(report["score"])

    def test_older_observation_rejected(self):
        with self.assertRaises(ValueError):
            self.adapter.observe(dict(self.obs), controller_phase="HOLD", expected_holding=True)

    def test_missing_or_stale_preflight_never_dispatches(self):
        for stale in (False, True):
            with self.subTest(stale=stale):
                self.setUp()
                flow = self.adapter.flow
                flow.detector_package_id = "fixture-package"
                now = time.monotonic()
                request = flow.on_detection({"schema": "observation-deviation-report/1", "method": METHOD,
                    "trial_id": "fixture", "observation_id": "alert", "generation": 0,
                    "motion_authorized": False, "captured_wall_s": now, "decision_wall_s": now,
                    "package_id": "fixture-package", "context_reference": "fixture-context",
                    "status": "ANOMALY", "score": 2., "raw_score": 2., "threshold": 1.},
                    now_wall_s=now, expected_holding=True)
                chain, robot, move = Mock(), Mock(), Mock()
                evidence = None if not stale else dict(trial_id="fixture", generation=0,
                    **{name: {"passed": True, "reference": "fixture-only", "measured_wall_s": now-2}
                       for name in ("authority", "measured_rest", "queue_empty", "macro_validated")})
                result = self.adapter.execute_macro(request, chain=chain, proposal={}, robot=robot,
                    original_move=move, preflight_evidence=evidence)
                self.assertEqual(result["kind"], "REQUEST_HALT_AND_HELP")
                chain.operation.assert_not_called()
                robot.set_both_hand_state.assert_not_called()
                move.assert_not_called()

    def request(self):
        self.adapter.flow.detector_package_id = "fixture-package"
        now = time.monotonic()
        report = dict(schema="observation-deviation-report/1", method=METHOD,
                      trial_id="fixture", observation_id="original-alert", generation=0,
                      captured_wall_s=now, decision_wall_s=now, observed_sim_s=1.,
                      package_id="fixture-package", context_reference="fixture-context",
                      motion_authorized=False, status="ANOMALY", score=2., raw_score=2., threshold=1.)
        request = self.adapter.flow.on_detection(report, now_wall_s=now, expected_holding=True)
        self.assertEqual(request["kind"], "REQUEST_RECOVERY_PREFLIGHT")
        return request

    def proposal(self):
        root = Path(self.directory.name)
        proposal = dict(trial_id="fixture", candidate_id="fixture-candidate",
                        orientation_wxyz=[1., 0., 0., 0.], retreat_world_m=[0., 0., .35],
                        pick_world_m=[0., 0., .02], lift_world_m=[0., 0., .3],
                        open_wait_steps=45, close_wait_steps=12)
        content = json.dumps(proposal).encode()
        (root / "macro-proposal.json").write_bytes(content)
        chain = Mock(trial_id="fixture", output=root,
                     decision=dict(trial_id="fixture", candidate_id="fixture-candidate",
                                   candidate_spec_reference="macro-proposal.json#sha256="+hashlib.sha256(content).hexdigest()))
        chain.trace.pending_feedback = []
        chain.trace.clock.return_value = {"sim_time_s": 5.}
        chain.operation.side_effect = lambda name, function, **kwargs: function()
        return chain, proposal

    def evidence(self):
        now = time.monotonic()
        return dict(trial_id="fixture", generation=0,
                    **{name: {"passed": True, "reference": "SOFTWARE-FIXTURE-ONLY", "measured_wall_s": now}
                       for name in ("authority", "measured_rest", "queue_empty", "macro_validated")})

    def test_proposal_target_tampering_cannot_dispatch_or_consume_budget(self):
        request = self.request()
        chain, proposal = self.proposal()
        proposal["pick_world_m"][2] = 5.
        robot, move = Mock(), Mock()
        result = self.adapter.execute_macro(request, chain=chain, proposal=proposal, robot=robot,
                                            original_move=move, preflight_evidence=self.evidence())
        self.assertEqual(result["kind"], "REQUEST_HALT_AND_HELP")
        self.assertEqual(self.adapter.flow.attempts, 0)
        chain.operation.assert_not_called()
        self.assertFalse(robot.mock_calls or move.mock_calls)
        log = (Path(self.directory.name)/"journal.jsonl").read_text()
        self.assertIn("PROPOSAL_CONTENT_MISMATCH", log)
        self.assertNotIn("MACRO_ACCEPTED", log)

    def test_proposal_file_hash_tampering_cannot_dispatch(self):
        request = self.request()
        chain, proposal = self.proposal()
        (Path(self.directory.name)/"macro-proposal.json").write_text(json.dumps(proposal)+" ")
        result = self.adapter.execute_macro(request, chain=chain, proposal=proposal, robot=Mock(),
                                            original_move=Mock(), preflight_evidence=self.evidence())
        self.assertEqual(result["kind"], "REQUEST_HALT_AND_HELP")
        chain.operation.assert_not_called()
        self.assertIn("PROPOSAL_FILE_HASH_MISMATCH", (Path(self.directory.name)/"journal.jsonl").read_text())

    def test_bound_macro_records_five_operations_but_does_not_resume(self):
        request = self.request()
        chain, proposal = self.proposal()
        robot, move = Mock(), Mock(return_value=True)
        result = self.adapter.execute_macro(request, chain=chain, proposal=proposal, robot=robot,
                                            original_move=move, preflight_evidence=self.evidence())
        self.assertEqual(result["kind"], "REQUEST_NEW_HOLD_OBSERVATIONS")
        self.assertEqual(self.adapter.flow.state, "VERIFYING")
        self.assertEqual(self.adapter.flow.attempts, 1)
        self.assertEqual([c.args[0] for c in chain.operation.call_args_list],
                         ["release", "retreat", "regrasp", "close", "lift"])
        self.assertEqual(move.call_count, 3)
        events = [json.loads(x) for x in (Path(self.directory.name)/"journal.jsonl").read_text().splitlines()]
        binding_event = next(e for e in events if "proposal_binding" in e)
        self.assertTrue(binding_event["proposal_binding"]["passed"])
        self.assertEqual(binding_event["proposal_binding"]["proposal_sha256"],
                         chain.decision["candidate_spec_reference"].split("=")[1])

    def test_fsync_delay_does_not_extend_preflight_evidence(self):
        request = self.request()
        chain, proposal = self.proposal()
        evidence = self.evidence()
        start = time.monotonic()
        with patch("official_pre_adapter.time.monotonic", side_effect=[start, start+2.]):
            result = self.adapter.execute_macro(request, chain=chain, proposal=proposal,
                robot=Mock(), original_move=Mock(), preflight_evidence=evidence)
        self.assertEqual(result["kind"], "REQUEST_HALT_AND_HELP")
        chain.operation.assert_not_called()

    def test_adapter_refresh_uses_actual_newest_frame_and_runtime(self):
        request = self.request()
        # Windows monotonic() may return the same tick for adjacent reads.
        # Use a controlled newer capture, rather than relying on fsync latency.
        now = self.adapter.flow.accepted_report["captured_wall_s"] + .1
        self.obs = dict(self.obs, observation_id="fresh", rendering_frame=2, rendering_time_s=1.1,
                        camera_read_end={"sim_time_s":1.1},
                        camera_read_begin={"wall_monotonic_ns":int(now*1e9)})
        self.trace.observations.append(self.obs)
        report = dict(self.adapter.flow.accepted_report, observation_id="fresh", observed_sim_s=1.1,
                      captured_wall_s=now, decision_wall_s=now)
        self.adapter.runtime.observe = Mock(return_value=report)
        with patch("official_pre_adapter.time.monotonic", return_value=now + .01):
            metadata, actual, event = self.adapter.refresh_preflight(self.obs)
        self.assertIs(actual, report)
        self.assertEqual(event["kind"], "PREFLIGHT_DETECTION_REFRESHED")
        self.assertEqual(event["request_id"], request["request_id"])
        self.assertEqual(metadata["phase"], "HOLD")
        self.assertEqual(self.adapter.runtime.observe.call_args.args[1], metadata)
        self.assertEqual(self.adapter.flow.attempts, 0)


class PreflightRefreshTests(unittest.TestCase):
    """Clock/provenance fixtures, not a real model or measured robot permission."""
    def setUp(self):
        self.events = []
        self.flow = DiagnosticRecoveryWorkflow("fixture", detector_package_id="package",
                                               context_reference="context", journal=self.events.append)
        self.old = dict(schema="observation-deviation-report/1", method=METHOD,
                        trial_id="fixture", observation_id="old", generation=0,
                        captured_wall_s=1., decision_wall_s=1.1, observed_sim_s=2.,
                        package_id="package", context_reference="context", motion_authorized=False,
                        status="ANOMALY", score=2., raw_score=2., threshold=1.)
        self.request = self.flow.on_detection(self.old, now_wall_s=1.1, expected_holding=True)
        self.new = dict(self.old, observation_id="new", captured_wall_s=10., decision_wall_s=10.1,
                        observed_sim_s=2.1)

    def refresh(self, report=None):
        return self.flow.refresh_preflight_detection(self.request["request_id"],
            self.new if report is None else report, now_wall_s=10.2)

    def test_fresh_alert_can_refresh_expired_request_without_resetting_identity(self):
        event = self.refresh()
        self.assertEqual(event["kind"], "PREFLIGHT_DETECTION_REFRESHED")
        self.assertEqual(self.flow.accepted_report, self.new)
        self.assertEqual((self.flow.generation,self.flow.attempts,self.flow.request_id),
                         (0,0,self.request["request_id"]))
        accepted = self.flow.begin_macro(self.request["request_id"], permit=dict(trial_id="fixture",
            generation=0, authority=True, measured_rest=True, queue_empty=True,
            macro_validated=True, now_wall_s=10.3))
        self.assertEqual(accepted["kind"], "MACRO_ACCEPTED")

    def test_invalid_refreshed_reports_fail_closed(self):
        bad = [dict(self.new, trial_id="other"), dict(self.new,generation=1),
               dict(self.new,package_id="other"), dict(self.new,context_reference="other"),
               dict(self.new,score=0.), dict(self.new,captured_wall_s=1.),
               dict(self.new,status="NORMAL",score=0.,raw_score=0.),
               dict(self.new,status="UNKNOWN",reason="WINDOW_WARMUP"),
               dict(self.new,observation_id="old"), dict(self.new,observed_sim_s=2.),
               dict(self.new,schema="invalid"),dict(self.new,motion_authorized=True)]
        for report in bad:
            with self.subTest(report=report):
                self.setUp()
                event = self.refresh(report)
                self.assertEqual(event["kind"], "REQUEST_HALT_AND_HELP")
                self.assertEqual(self.flow.attempts, 0)
                self.assertEqual(self.flow.accepted_report, self.old)
                self.assertEqual(self.flow.begin_macro(self.request["request_id"],permit={})["kind"],"REJECT")

    def test_refresh_journal_failure_leaves_previous_report(self):
        def fail(event):
            raise OSError("fixture journal failure")
        self.flow.journal = fail
        with self.assertRaises(OSError):
            self.refresh()
        self.assertEqual(self.flow.accepted_report, self.old)
        self.assertEqual(self.flow.attempts, 0)

    def test_refresh_after_revocation_rejected(self):
        self.flow.revoke()
        self.assertEqual(self.refresh()["kind"], "REJECT")
        self.assertEqual(self.flow.generation, 1)
        self.assertEqual(self.flow.accepted_report, self.old)


if __name__ == "__main__":
    unittest.main()
