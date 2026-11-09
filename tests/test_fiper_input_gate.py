"""Software fixtures only, not FIPER accuracy or robot performance evidence."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "simulation"))
from fiper_input_gate import check_fiper_inputs, recovery_gate


class FiperInputGateTests(unittest.TestCase):
    def test_missing_real_inputs_stays_unknown(self):
        report = check_fiper_inputs({"observation_id": "fixture", "observation_clock": {}})
        self.assertEqual(report["status"], "UNKNOWN")
        self.assertEqual(len(report["missing"]), 5)
        self.assertFalse(report["scores_computed"])
        self.assertEqual(recovery_gate(report, expected_hold=True, attempts_remaining=1,
                                       action_inflight=False), "HELP_NO_NEW_DISPATCH")

    def test_observation_branch_does_not_require_policy_or_action_samples(self):
        packet = dict.fromkeys(("encoder_ref", "preprocessing_ref", "obs_embeddings",
                                "rnd_checkpoint_ref", "calibration_ref"), "fixture")
        packet.update(observation_id="fixture", observation_clock={}, obs_embeddings=[0.1, 0.2])
        self.assertEqual(check_fiper_inputs(packet)["missing"], [])
        self.assertEqual(check_fiper_inputs(packet)["reason"], "OFFICIAL_BACKEND_AND_CALIBRATION_NOT_BOUND")

    def test_unverified_normal_does_not_unlock_continuation(self):
        self.assertEqual(recovery_gate({"status": "NORMAL"}, expected_hold=True,
                                       attempts_remaining=1, action_inflight=False), "HELP_NO_NEW_DISPATCH")

    def test_planned_release_does_not_request_recovery(self):
        self.assertEqual(recovery_gate({"status": "UNKNOWN"}, expected_hold=False,
                                       attempts_remaining=1, action_inflight=False), "CONTINUE_PLANNED_RELEASE")

    def test_budget_and_action_gate(self):
        report = {"status": "ANOMALY", "scores_computed": True, "calibration_verified": True}
        self.assertEqual(recovery_gate(report, expected_hold=True, attempts_remaining=0,
                                       action_inflight=False), "HELP_NO_NEW_DISPATCH")
        self.assertEqual(recovery_gate(report, expected_hold=True, attempts_remaining=1,
                                       action_inflight=True), "WAIT_FOR_ACTION_COMPLETION")


if __name__ == "__main__":
    unittest.main()
