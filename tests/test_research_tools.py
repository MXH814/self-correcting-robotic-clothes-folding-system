import copy
import math
import unittest
from dataclasses import replace
from research_tools.diagnostics import (DataError, Ranker, calibration_metrics, evaluate,
                                       grouped_split, paired_bootstrap, synthetic, validate, wilson)
from research_tools.recovery_gate import Context, select_candidate
from research_tools.resources import estimate


class DataTests(unittest.TestCase):
    def setUp(self):
        self.rows = synthetic()

    def test_fixture_deterministic(self):
        self.assertEqual(self.rows, synthetic())
        self.assertEqual(evaluate(self.rows), evaluate(self.rows))
        self.assertEqual(evaluate(self.rows)["purpose"], "synthetic")

    def test_reject_leakage(self):
        self.rows[0]["split"] = "sealed_test"
        with self.assertRaisesRegex(DataError, "leakage"):
            validate(self.rows)

    def test_sealed_test_rejected(self):
        root = self.rows[0]["root_id"]
        for r in self.rows:
            if r["root_id"] == root:
                r["split"] = "sealed_test"
        with self.assertRaisesRegex(DataError, "sealed"):
            evaluate(self.rows)
        with self.assertRaisesRegex(DataError, "sealed"):
            grouped_split(self.rows)

    def test_privileged_and_future_rejected(self):
        for field, value in (("privileged", True), ("uses_future", True), ("latest_sim_s", 3.)):
            rows = copy.deepcopy(self.rows)
            rows[0]["feature_provenance"]["current"][field] = value
            with self.assertRaises(DataError):
                validate(rows)

    def test_unknown_feature_block(self):
        self.rows[0]["features"]["hidden_mesh"] = [0.]
        with self.assertRaises(DataError):
            validate(self.rows)

    def test_outcome_requires_execution(self):
        self.rows[0]["executed"] = False
        with self.assertRaises(DataError):
            validate(self.rows)

    def test_false_success(self):
        r = next(r for r in self.rows if r["autonomous_success"])
        r["assisted"] = True
        with self.assertRaises(DataError):
            validate(self.rows)

    def test_nonfinite(self):
        self.rows[0]["features"]["current"] = [math.nan]
        with self.assertRaises(DataError):
            validate(self.rows)

    def test_connected_split(self):
        for r in self.rows:
            r["split"] = "development"
            if r["root_id"] in ("synthetic-root-00", "synthetic-root-01"):
                r["family_id"] = "shared-family"
        output = grouped_split(self.rows)
        self.assertEqual(len({r["split"] for r in output if r["family_id"] == "shared-family"}), 1)

    def test_train_only_scaling(self):
        train = [r for r in self.rows if r["split"] == "train"]
        model = Ranker(train, "B0")
        before = model.mean[:]
        row = copy.deepcopy(self.rows[0])
        row["features"]["current"] = [1e10]
        model.score(row)
        self.assertEqual(model.mean, before)
        with self.assertRaises(DataError):
            Ranker([r for r in self.rows if r["split"] == "development"], "B0")

    def test_unknown_pool_not_silently_failure(self):
        dev = next(r for r in self.rows if r["split"] == "development")
        dev["executed"] = False
        dev["local_success"] = dev["autonomous_success"] = None
        report = evaluate(self.rows)
        b = report["summary"]["B0"]
        self.assertLess(b["paired_complete_roots"], b["all_roots"])

    def test_external_predictions_complete_and_unambiguous(self):
        predictions = [{"root_id": r["root_id"], "candidate_id": r["candidate_id"], "method": m,
                        "score": float(r["candidate_id"]), "score_semantics": "rank_only"}
                       for r in self.rows if r["split"] == "development" and r["eligible"]
                       for m in ("B0", "B1", "B2", "B3", "B4")]
        self.assertEqual(evaluate(self.rows, external_predictions=predictions)["ranking_backend"], "external_rank_scores")
        with self.assertRaises(DataError):
            evaluate(self.rows, external_predictions=predictions[:-1])
        with self.assertRaises(DataError):
            evaluate(self.rows, external_predictions=predictions + [predictions[0]])

    def test_wilson_and_bootstrap(self):
        self.assertIsNone(wilson(0, 0))
        low, high = wilson(5, 10)
        self.assertLess(low, .5)
        self.assertGreater(high, .5)
        self.assertEqual(paired_bootstrap([("a", 1), ("b", 1)]), [1., 1.])

    def test_calibration_separate_and_correct(self):
        records = [{"root_id": str(i), "candidate_id": "a", "split": "validation",
                    "probability": p, "success": y, "calibrator_fit_disjoint": True}
                   for i, (p, y) in enumerate(((.2, False), (.8, True)))]
        result = calibration_metrics(records)
        self.assertAlmostEqual(result["brier"], .04)
        self.assertFalse(result["dispatch_authorized"])
        records[0]["split"] = "sealed_test"
        with self.assertRaises(DataError):
            calibration_metrics(records)


class GateTests(unittest.TestCase):
    def setUp(self):
        self.ctx = Context(1, 10., 9.5, 9.6, 0, 0., 0., .25, True, False,
                           "p", "c", "m", "cal", ("joint",), (-1.,), (1.,), .5)
        self.candidate = {"candidate_id": "a", "channels": ["joint"], "values": [.2],
                          "prefix_duration_sim_s": .1, "score": .7,
                          "score_semantics": "conditional_full_task_success", "calibration_ref": "cal",
                          "continuation_version": "c", "policy_version": "m"}
        self.decision = {"control_generation": 1, "profile_version": "p", "candidates": [self.candidate]}

    def test_valid_is_not_dispatch_and_no_count_change(self):
        self.assertEqual(select_candidate(self.decision, self.ctx), ("a", "PREFLIGHT_ONLY"))
        self.assertEqual(self.ctx.attempts, 0)

    def test_stop_generation_and_authority(self):
        for ctx in (replace(self.ctx, stop_pending=True), replace(self.ctx, generation=2),
                    replace(self.ctx, authority=False)):
            self.assertIsNone(select_candidate(self.decision, ctx)[0])

    def test_time_and_budget(self):
        for ctx in (replace(self.ctx, observation_s=8.), replace(self.ctx, observation_s=11.),
                    replace(self.ctx, attempts=3), replace(self.ctx, cost=.25),
                    replace(self.ctx, active_sim_s=300.), replace(self.ctx, now_s=math.nan)):
            self.assertIsNone(select_candidate(self.decision, ctx)[0])

    def test_score_and_action_filter(self):
        for field, value in (("values", [math.inf]), ("values", [2.]), ("score", .59),
                             ("score_semantics", "rank_only"), ("calibration_ref", "unknown"),
                             ("prefix_duration_sim_s", 1.), ("continuation_version", "other")):
            d = copy.deepcopy(self.decision)
            d["candidates"][0][field] = value
            self.assertIsNone(select_candidate(d, self.ctx)[0])

    def test_entire_oversized_or_duplicate_pool_rejected(self):
        self.decision["candidates"] *= 9
        self.assertEqual(select_candidate(self.decision, self.ctx)[1], "TOO_MANY_CANDIDATES")
        self.decision["candidates"] = self.decision["candidates"][:2]
        self.assertEqual(select_candidate(self.decision, self.ctx)[1], "INVALID_SCHEMA")

    def test_highest_qualified(self):
        bad = dict(self.candidate, candidate_id="bad", score=.99, values=[5.])
        good = dict(self.candidate, candidate_id="good", score=.8)
        self.decision["candidates"] += [bad, good]
        self.assertEqual(select_candidate(self.decision, self.ctx)[0], "good")


class ResourceTests(unittest.TestCase):
    def test_units(self):
        result = estimate(10, 2, 3, 60., 1., 5., 1000, 0.)
        self.assertEqual(result["branch_rollouts"], 60)
        self.assertEqual(result["estimated_cost_same_currency_as_input"], 10.)
        self.assertEqual(result["estimated_bytes"], 60000)

    def test_reject_bad_counts(self):
        with self.assertRaises(ValueError):
            estimate(10, 9, 1, 60., 1., 5., 1000)


if __name__ == "__main__":
    unittest.main()
