"""Causality and integrity tests; altered copies are software fixtures only."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from research_tools.action_chain_intake import export_chain, history_for_decision, read_chain
from research_tools.diagnostics import DataError, validate
from research_tools.runtime_intake import digest

SOURCE = Path(__file__).resolve().parents[1] / "docs/research/zhangmingbo/preaction-chain-20261108"


class ActionChainTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "altered-fixture"
        shutil.copytree(SOURCE, self.source)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, data):
        (self.source / name).write_text(json.dumps(data), encoding="utf-8")

    def modify_chain(self, change):
        chain = json.loads((self.source / "action-chain.json").read_text())
        change(chain)
        self.write("action-chain.json", chain)
        self.resign()

    def resign(self):
        """Update fixture hashes so semantic tests are not just checksum failures."""
        files = {p.name: {"size_bytes": p.stat().st_size, "sha256": digest(p)}
                 for p in self.source.iterdir() if p.name != "manifest.json"}
        self.write("manifest.json", files)

    def test_real_chain_feature_blocks_and_causal_boundary(self):
        context, segment, report = read_chain(SOURCE)
        self.assertEqual(report["verified_files"], 6)
        self.assertEqual(context["block_dimensions"], {"rgb_grid": 192, "joint_q_dq": 120, "masked_candidate": 180})
        self.assertEqual(len(context["current"]), 492)
        self.assertIsNone(context["executed_action_history"])
        self.assertIsNone(context["visual_history"])
        self.assertIsNone(context["stage_budget"])
        self.assertTrue(report["pre_command_rgb_available"])
        self.assertEqual(report["segment_steps"], 60)
        self.assertEqual(report["feedback_samples"], 4)
        self.assertAlmostEqual(report["render_to_read_age_sim_s"], 1 / 30, places=6)
        self.assertFalse(report["diagnostic_dataset_ready"])
        self.assertFalse(context["online_authorized"])
        with self.assertRaises(DataError):
            validate([context])

    def test_current_segment_cannot_enter_its_own_decision_history(self):
        context, segment, _ = read_chain(SOURCE)
        with self.assertRaisesRegex(DataError, "future execution"):
            history_for_decision(segment, context["task_id"], context["generation"], context["as_of"])
        vector = history_for_decision(segment, context["task_id"], context["generation"], segment["available_after"])
        self.assertEqual(len(vector), 242)
        with self.assertRaisesRegex(DataError, "different task"):
            history_for_decision(segment, "unrelated", context["generation"], segment["available_after"])
        with self.assertRaisesRegex(DataError, "generation boundary"):
            history_for_decision(segment, context["task_id"], 1, segment["available_after"])

    def test_checksum_failure_prevents_output_creation(self):
        (self.source / "pre-action-rgb.png").write_bytes(b"corrupt")
        output = self.root / "output"
        with self.assertRaises(DataError):
            export_chain(self.source, output)
        self.assertFalse(output.exists())

    def test_future_camera_and_after_command_capture_rejected(self):
        for change in (
            lambda c: c["observation"]["camera"].update(rendering_time_s=5.),
            lambda c: c["observation"]["camera"]["read_end"].update(wall_monotonic_ns=10**18),
        ):
            shutil.copyfile(SOURCE / "action-chain.json", self.source / "action-chain.json")
            self.modify_chain(change)
            with self.assertRaises(DataError):
                read_chain(self.source)

    def test_mixed_run_profile_or_generation_rejected(self):
        for change in (
            lambda c: c.update(run_id="other-run"),
            lambda c: c["joint_profile"].update(sha256="0" * 64),
            lambda c: c["execution"].update(control_generation=1),
            lambda c: c["joint_profile"]["left_names"].reverse(),
        ):
            shutil.copyfile(SOURCE / "action-chain.json", self.source / "action-chain.json")
            self.modify_chain(change)
            with self.assertRaises(DataError):
                read_chain(self.source)

    def test_durable_intent_and_feedback_must_match(self):
        for change in (
            lambda c: c["action"].update(target=0.),
            lambda c: c["execution"].update(measured_step_delta=59),
            lambda c: c["execution"].update(measured_joint_delta_rad=.1),
            lambda c: c["execution"]["measured_feedback"][0]["right_positions"].__setitem__(0, 7.),
        ):
            shutil.copyfile(SOURCE / "action-chain.json", self.source / "action-chain.json")
            self.modify_chain(change)
            with self.assertRaises(DataError):
                read_chain(self.source)

    def test_future_feedback_change_does_not_change_decision_input(self):
        before, segment, _ = read_chain(self.source)
        sample = json.loads((self.source / "sample.json").read_text())
        chain = json.loads((self.source / "action-chain.json").read_text())
        sample["observations"][-1]["right_positions"][1] += .01
        chain["execution"]["measured_feedback"] = sample["observations"][1:]
        self.write("sample.json", sample)
        chain["joint_profile"]["sha256"] = digest(self.source / "sample.json")
        self.write("action-chain.json", chain)
        self.resign()
        after, changed_segment, _ = read_chain(self.source)
        self.assertEqual(before, after)
        self.assertNotEqual(segment["measured_joint_displacement_rad"], changed_segment["measured_joint_displacement_rad"])

    def test_inventory_path_escape_rejected(self):
        manifest = json.loads((self.source / "manifest.json").read_text())
        manifest["../escape.json"] = {"size_bytes": 0, "sha256": "0" * 64}
        self.write("manifest.json", manifest)
        with self.assertRaisesRegex(DataError, "outside/missing"):
            read_chain(self.source)

    def test_fresh_output_and_manifest_hashes(self):
        output = self.root / "output"
        export_chain(SOURCE, output)
        manifest = json.loads((output / "manifest.json").read_text())
        for name, expected in manifest["files"].items():
            self.assertEqual(digest(output / name), expected)
        with self.assertRaises(FileExistsError):
            export_chain(SOURCE, output)
        with self.assertRaises(DataError):
            export_chain(self.source, self.source / "bad-output")


if __name__ == "__main__":
    unittest.main()
