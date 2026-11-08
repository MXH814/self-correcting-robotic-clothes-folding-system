"""Software-only negative checks; these fixtures are not robot evidence."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "simulation"))
from verify_fold_recovery_chain import validate_binding


def timestamp(step):
    return {"sim_step": step, "sim_time_s": step / 60, "wall_monotonic_ns": step * 1000000}


def fixture():
    proposal = {"schema": "recovery-macro-proposal/1", "kind": "release-retreat-regrasp-lift",
                "trial_id": "fixture-trial", "candidate_id": "candidate", "source_reference": "synthetic fixture",
                "available_at": timestamp(7), "arm": "left", "coordinate_frame": "world", "position_unit": "m",
                "retreat_world_m": [0., 0., .35], "pick_world_m": [0., 0., .02],
                "lift_world_m": [0., 0., .3], "orientation_wxyz": [1., 0., 0., 0.],
                "open_wait_steps": 45, "close_wait_steps": 12}
    decision = {"trial_id": "fixture-trial", "candidate_id": "candidate", "lineage_group": "fixture-trial",
                "proposal_persisted_at": timestamp(8), "decision_at": timestamp(10),
                "observation_id": "obs", "continuation_success": None, "label_review_reference": None}
    trace = {"trial_id": "fixture-trial", "scope": "complete_fold_tops_diagnostic_recovery",
             "observations": [{"observation_id": "obs", "joint_read_end": timestamp(9)}], "actions": [],
             "boundaries": [{"phase": p} for p in ("upstream-stage-1-end", "upstream-stage-2-end",
                             "upstream-stage-3-end", "fixed-upstream-continuation", "final-evidence")]}
    execution = []
    for i, name in enumerate(("release", "retreat", "regrasp", "close", "lift")):
        begin = 11 + 100 * i
        key = {"retreat": "retreat_world_m", "regrasp": "pick_world_m", "lift": "lift_world_m"}.get(name)
        requested = ({"target_world_m": proposal[key], "orientation_wxyz": proposal["orientation_wxyz"],
                      "dense_sample_scale_m": .01} if key else {"hand_state": "open" if name == "release" else "close"})
        execution.append({"operation": name, "candidate_id": "candidate", "begin": timestamp(begin),
                          "end": timestamp(begin + 70), "command_ids": [str(i)], "sdk_result": True if key else None,
                          "extra_wait_steps": 45 if name == "release" else 12 if name == "close" else 0,
                          "requested": requested})
        trace["actions"].append({"command_id": str(i), "arm": "left", "phase": "macro-" + name,
                                 "observation_id": "obs", "issue": timestamp(begin + 1),
                                 "api_returned": timestamp(begin + 2)})
    record = {"trial_id": "fixture-trial", "macro_execution": execution, "resume_sdk_result": True,
              "checkpoints": {"final": timestamp(600)}, "judgment": {"minimum_ratio": .88}}
    context = {"trial_id": "fixture-trial", "budget": {"diagnostic_macro_attempts": 1, "retry_count": 0},
               "target": {"minimum_ratio": .88}, "controller": {"macro_motion_sample_scale_m": .01}}
    return record, trace, proposal, decision, context


class FullRecoveryBindingTests(unittest.TestCase):
    def test_valid_binding(self):
        self.assertEqual(validate_binding(*fixture()), ("0", 5))

    def test_reject_cross_trial_outcome(self):
        args = fixture()
        args[0]["trial_id"] = "another-run"
        with self.assertRaisesRegex(ValueError, "cross-trial"):
            validate_binding(*args)

    def test_reject_retrospective_proposal(self):
        args = fixture()
        args[2]["available_at"] = timestamp(20)
        with self.assertRaisesRegex(ValueError, "retrospective"):
            validate_binding(*args)

    def test_reject_missing_retreat(self):
        args = fixture()
        args[0]["macro_execution"].pop(1)
        with self.assertRaisesRegex(ValueError, "incomplete"):
            validate_binding(*args)

    def test_reject_changed_execution_target(self):
        args = copy.deepcopy(fixture())
        args[0]["macro_execution"][2]["requested"]["target_world_m"] = [.5, 0., .02]
        with self.assertRaisesRegex(ValueError, "target differs"):
            validate_binding(*args)

    def test_reject_self_signed_label(self):
        args = fixture()
        args[3]["continuation_success"] = True
        with self.assertRaisesRegex(ValueError, "independent label"):
            validate_binding(*args)

    def test_reject_no_actual_release(self):
        args = fixture()
        args[0]["macro_execution"][0]["command_ids"] = []
        with self.assertRaisesRegex(ValueError, "no actual dispatch"):
            validate_binding(*args)


if __name__ == "__main__":
    unittest.main()
