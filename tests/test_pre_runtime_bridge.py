"""Synthetic interface tests; no real detector accuracy claims."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "simulation"))
from pre_runtime_bridge import PreRuntimeBridge


def observation(step=1):
    return {"trial_id": "software-fixture", "observation_id": str(step), "phase": "lift",
            "capture_clock": {"sim_time_s": step, "wall_monotonic_ns": step * 100},
            "injection": "must_not_reach_detector", "judgment": True}


def result(obs, state):
    return {"trial_id": obs["trial_id"], "observation_id": obs["observation_id"], "status": state,
            "score": 1., "threshold": .5, "method": "SOFTWARE_STUB", "model_ref": "fixture",
            "threshold_ref": "fixture", "preprocessing_ref": "fixture"}


class BridgeTests(unittest.TestCase):
    def test_missing_detector_does_not_dispatch(self):
        bridge = PreRuntimeBridge(execute_macro=lambda *a: self.fail("unexpected action"))
        self.assertEqual(bridge.handle(observation(), expected_hold=True), "HELP_NO_NEW_DISPATCH")
        self.assertTrue(bridge.locked)

    def test_normal_no_macro_and_no_injection_leak(self):
        def detect(obs):
            self.assertNotIn("injection", obs)
            self.assertNotIn("judgment", obs)
            return result(obs, "NORMAL")
        bridge = PreRuntimeBridge(detect=detect, execute_macro=lambda *a: self.fail("unexpected macro"))
        self.assertEqual(bridge.handle(observation(), expected_hold=True), "CONTINUE")

    def test_anomaly_checks_new_observation_before_continue(self):
        events = []
        bridge = PreRuntimeBridge(detect=lambda o: result(o, "ANOMALY"),
            execute_macro=lambda *a: {"completed": True}, observe_after=lambda: observation(2),
            check_after=lambda o: result(o, "NORMAL"), emit=events.append)
        self.assertEqual(bridge.handle(observation(), expected_hold=True), "CONTINUE_AFTER_RECOVERY")
        self.assertEqual([x["kind"] for x in events],
                         ["DETECTION", "RECOVERY_REQUEST", "RECOVERY_EXECUTION", "RECOVERY_CHECK", "CONTINUE"])
        self.assertEqual(bridge.handle(observation(), expected_hold=True), "DUPLICATE_NO_DISPATCH")

    def test_failed_unknown_or_stale_postcheck_cannot_continue(self):
        for state, fresh in (("ANOMALY", observation(2)), ("UNKNOWN", observation(2)), ("NORMAL", observation())):
            bridge = PreRuntimeBridge(detect=lambda o: result(o, "ANOMALY"),
                execute_macro=lambda *a: {"completed": True}, observe_after=lambda: fresh,
                check_after=lambda o: result(o, state))
            self.assertEqual(bridge.handle(observation(), expected_hold=True), "HELP_NO_NEW_DISPATCH")

    def test_planned_release_inflight_budget_and_wrong_trial(self):
        bridge = PreRuntimeBridge()
        self.assertEqual(bridge.handle(observation(), expected_hold=False), "CONTINUE_PLANNED_RELEASE")
        self.assertEqual(bridge.handle(observation(), expected_hold=True, action_inflight=True), "WAIT_FOR_ACTION_COMPLETION")
        bridge = PreRuntimeBridge(detect=lambda o: result(o, "ANOMALY"), attempts=0)
        self.assertEqual(bridge.handle(observation(), expected_hold=True), "HELP_NO_NEW_DISPATCH")
        bridge = PreRuntimeBridge(detect=lambda o: {**result(o, "NORMAL"), "trial_id": "other"})
        self.assertEqual(bridge.handle(observation(), expected_hold=True), "HELP_NO_NEW_DISPATCH")


if __name__ == "__main__":
    unittest.main()
