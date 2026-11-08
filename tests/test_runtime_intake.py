"""Offline regressions on committed component records and intentionally altered copies.

Altered records are negative software fixtures, never experimental observations.
"""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from research_tools.diagnostics import DataError, validate
from research_tools.runtime_intake import (audit_control, camera_evidence, digest,
                                         encode_joint_target, encode_sample, export_intake)

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "docs/research/zhangmingbo/runtime-io-camera-20261108/sample.json"
CONTROL = ROOT / "docs/research/zhangmingbo/fold-experiments-20261108/control-evidence.json"


class RuntimeIntakeTests(unittest.TestCase):
    def setUp(self):
        self.sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
        self.temp = tempfile.TemporaryDirectory()
        self.output = Path(self.temp.name) / "new-output"

    def tearDown(self):
        self.temp.cleanup()

    def test_measured_channel_identity_and_sparse_command(self):
        profile, cmd, rows = encode_sample(self.sample)
        names = [d["channel"] for d in profile["channels"]]
        self.assertEqual(len(names), 60)
        self.assertEqual(len(set(names)), 60)
        self.assertIn("left:shoulder_pan_joint", names)
        self.assertIn("right:shoulder_pan_joint", names)
        self.assertEqual(sum(cmd["mask"]), 1)
        self.assertAlmostEqual(cmd["delta_from_measured_rad"][0], .03)
        self.assertEqual(len(cmd["feature_vector"]), 180)
        self.assertEqual(cmd["absolute_rad"][1:], [0.] * 59)
        self.assertTrue(cmd["uncommanded_zero_is_padding_not_target"])
        self.assertEqual(len(rows[0]["joint_feature"]), 120)
        self.assertFalse(profile["legacy_joint_order_verified"])

    def test_future_feedback_cannot_change_before_command_features(self):
        _, cmd, first = encode_sample(self.sample)
        changed = copy.deepcopy(self.sample)
        changed["observations"][-1]["left_positions"][0] += .5
        _, newcmd, second = encode_sample(changed)
        self.assertEqual(first[0], second[0])
        self.assertEqual(cmd, newcmd)
        self.assertEqual(first[-1]["past_joint_feature"], second[-1]["past_joint_feature"])
        self.assertNotEqual(first[-1]["joint_feature"], second[-1]["joint_feature"])

    def test_unexecuted_right_arm_candidate_uses_correct_channel_and_no_fake_feedback(self):
        profile, _, _ = encode_sample(self.sample)
        o = self.sample["observations"][0]
        q = o["left_positions"] + o["right_positions"]
        candidate = encode_joint_target(profile, q, "right", 0, q[30] + .02)
        self.assertEqual(candidate["mask"].index(1), 30)
        self.assertEqual(candidate["commanded_channel"], "right:shoulder_pan_joint")
        self.assertAlmostEqual(candidate["delta_from_measured_rad"][30], .02)
        self.assertNotIn("api_returned", candidate)
        self.assertNotIn("autonomous_success", candidate)
        self.assertFalse(candidate["online_authorized"])
        with self.assertRaises(DataError):
            encode_joint_target(profile, q, "right", 50, 0.)

    def test_history_padding_and_no_false_executed_or_recovery_labels(self):
        _, _, rows = encode_sample(self.sample)
        self.assertEqual(rows[0]["history_mask"], [False] * 4)
        self.assertEqual(rows[-1]["history_mask"], [True] * 4)
        for row in rows:
            self.assertIsNone(row["rgb_feature"])
            self.assertIsNone(row["executed_action_history"])
            self.assertIsNone(row["autonomous_success"])
            self.assertFalse(row["online_authorized"])
        with self.assertRaises(DataError):
            validate(rows)

    def test_joint_units_names_and_command_limits_rejected(self):
        for mutate in (lambda s: s["left_dofs"][0].update(position_unit="degree"),
                       lambda s: s["command"].update(joint_name="wrong_joint"),
                       lambda s: s["command"].update(target=1000),
                       lambda s: s["command"].update(joint_index=True)):
            altered = copy.deepcopy(self.sample)
            mutate(altered)
            with self.assertRaises(DataError):
                encode_sample(altered)

    def test_reversed_clock_nonfinite_values_and_duplicate_indices_rejected(self):
        mutations = (lambda s: s["observations"][1]["capture_begin"].update(wall_monotonic_ns=0),
                     lambda s: s["observations"][0]["left_positions"].__setitem__(1, float("nan")),
                     lambda s: s["left_dofs"][1].update(index=0),
                     lambda s: s["command"]["issued"].update(sim_step=0))
        for mutate in mutations:
            altered = copy.deepcopy(self.sample)
            mutate(altered)
            with self.assertRaises(DataError):
                encode_sample(altered)

    def test_post_command_camera_is_inspection_not_pre_command_input(self):
        c = camera_evidence(self.sample, SAMPLE.parent)
        self.assertEqual(c["status"], "nonuniform")
        self.assertEqual(len(c["grid_feature"]), 192)
        self.assertAlmostEqual(c["age_at_read_sim_s"], .05, places=6)
        self.assertFalse(c["pre_command_rgb_available"])
        self.assertEqual(c["role"], "post_command_inspection_only")

    def test_camera_corruption_and_path_escape_rejected(self):
        self.sample["camera"]["rgb_min"] = -1
        with self.assertRaisesRegex(DataError, "statistics"):
            camera_evidence(self.sample, SAMPLE.parent)
        self.sample["camera"]["image"] = "../elsewhere.png"
        with self.assertRaisesRegex(DataError, "outside"):
            camera_evidence(self.sample, SAMPLE.parent)

    def test_black_camera_kept_as_failure_evidence(self):
        path = SAMPLE.parent.parent / "runtime-io-20261108/sample.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        c = camera_evidence(data, path.parent)
        self.assertEqual(c["status"], "all_black")
        self.assertIsNone(c["grid_feature"])

    def test_export_hashes_no_overwrite_and_no_in_place_output(self):
        report = export_intake(SAMPLE, self.output, CONTROL)
        self.assertFalse(report["diagnostic_dataset_ready"])
        self.assertFalse(report["online_authorized"])
        manifest = json.loads((self.output / "manifest.json").read_text())
        for name, expected in manifest["files"].items():
            self.assertEqual(digest(self.output / name), expected)
        original = (self.output / "manifest.json").read_bytes()
        with self.assertRaises(FileExistsError):
            export_intake(SAMPLE, self.output)
        self.assertEqual((self.output / "manifest.json").read_bytes(), original)
        with self.assertRaises(DataError):
            export_intake(SAMPLE, SAMPLE.parent / "invalid-output")

    def test_control_both_windows_and_scope_limits(self):
        report = audit_control(CONTROL)
        self.assertEqual([c["window_samples"] for c in report["cases"]], [7, 8])
        self.assertTrue(all(c["confirmed_in_component_probe"] for c in report["cases"]))
        self.assertFalse(report["srs_tests_accepted"])
        self.assertFalse(report["product_coordinator_verified"])

    def write_control(self, data):
        path = Path(self.temp.name) / "altered-control.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_control_weakened_conditions_or_nonfinite_speed_rejected(self):
        data = json.loads(CONTROL.read_text())
        data["threshold_rad_s"] = .1
        with self.assertRaisesRegex(DataError, "criteria"):
            audit_control(self.write_control(data))
        data = json.loads(CONTROL.read_text())
        proof = next(e for e in data["events"] if e["event"] == "rest_confirmed")
        proof["samples"][0]["velocities_rad_s"][0] = float("nan")
        with self.assertRaisesRegex(DataError, "speed channels"):
            audit_control(self.write_control(data))

    def test_control_mismatched_request_missing_barrier_and_empty_window_rejected(self):
        for mutation in (lambda d: next(e for e in d["events"] if e["event"] == "rest_confirmed").update(request_id="unknown"),
                         lambda d: d.update(events=[e for e in d["events"] if e["event"] != "probe_adapter_barrier_ack"]),
                         lambda d: next(e for e in d["events"] if e["event"] == "rest_confirmed").update(accepted_window=[])):
            data = json.loads(CONTROL.read_text())
            mutation(data)
            with self.assertRaises(DataError):
                audit_control(self.write_control(data))
        data = json.loads(CONTROL.read_text())
        proof = next(e for e in data["events"] if e["event"] == "rest_confirmed")
        request = next(e for e in data["events"] if e["event"] == "halt_accepted")
        proof["samples"][0]["wall_perf_counter_ns"] = request["wall_perf_counter_ns"] + 1
        with self.assertRaisesRegex(DataError, "precede generation barrier"):
            audit_control(self.write_control(data))

    def test_unconfirmed_stop_stays_unconfirmed(self):
        data = json.loads(CONTROL.read_text())
        proof = [e for e in data["events"] if e["event"] == "rest_confirmed"][-1]
        proof.update(event="rest_unconfirmed", accepted_window=[])
        report = audit_control(self.write_control(data))
        self.assertFalse(report["cases"][-1]["confirmed_in_component_probe"])
        self.assertIsNone(report["cases"][-1]["max_speed_rad_s"])


if __name__ == "__main__":
    unittest.main()
