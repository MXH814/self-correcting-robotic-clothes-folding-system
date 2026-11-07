import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from research_tools.diagnostics import DataError
from research_tools.legacy_observations import digest, history_window, load_export, validate_rows
from research_tools.handoff_audit import audit
from tools.simulation.export_numeric_trajectory import export

HAS_NUMPY = importlib.util.find_spec("numpy") is not None


@unittest.skipUnless(HAS_NUMPY, "NumPy optional legacy import dependency")
class LegacyTests(unittest.TestCase):
    def setUp(self):
        import numpy as np
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "manufactured.npz"
        records = np.array([{"joint_state": np.arange(60, dtype=np.float32) + i,
                             "image": np.full((2, 3, 3), i, dtype=np.uint8),
                             "garment_point_cloud": np.zeros((4, 3))} for i in range(3)], dtype=object)
        np.savez(self.source, **{s: records for s in ("stage_1", "stage_2", "stage_3")})
        self.hash = digest(self.source)
        self.output = self.root / "export"

    def tearDown(self):
        self.temp.cleanup()

    def make_export(self):
        result = export(self.source, self.output, self.hash, trusted=True)
        self.assertEqual(result["frames"], 9)
        return load_export(self.output)

    def test_trust_flag_required_before_load(self):
        with self.assertRaisesRegex(ValueError, "trust"):
            export(self.source, self.output, self.hash)
        self.assertFalse(self.output.exists())

    def test_hash_refused_before_output(self):
        with self.assertRaisesRegex(ValueError, "hash"):
            export(self.source, self.output, "0" * 64, trusted=True)
        self.assertFalse(self.output.exists())

    def test_round_trip_and_no_invented_labels(self):
        rows = self.make_export()
        self.assertFalse(rows[0]["online_authorized"])
        self.assertIsNone(rows[0]["action"])
        self.assertIsNone(rows[0]["sim_time_s"])
        self.assertIsNone(rows[0]["autonomous_success"])
        self.assertNotIn("garment_point_cloud", rows[0])

    def test_no_overwrite(self):
        self.make_export()
        original = (self.output / "manifest.json").read_bytes()
        with self.assertRaises(FileExistsError):
            export(self.source, self.output, self.hash, trusted=True)
        self.assertEqual((self.output / "manifest.json").read_bytes(), original)

    def test_history_never_uses_current_or_future(self):
        rows = self.make_export()
        w = history_window(rows, 2)
        self.assertEqual(w["mask"], [False, False, True, True])
        self.assertEqual(w["previous_frame_ids"][-1], rows[1]["frame_id"])
        self.assertNotIn(rows[2]["frame_id"], w["previous_frame_ids"])

    def test_stage_history_resets(self):
        rows = self.make_export()
        self.assertEqual(history_window(rows, 3)["mask"], [False] * 4)
        self.assertEqual(history_window(rows, 4)["mask"], [False, False, False, True])

    def test_reject_forged_legacy_time(self):
        rows = self.make_export()
        rows[0]["sim_time_s"] = 0.
        with self.assertRaisesRegex(DataError, "unknown"):
            validate_rows(rows)

    def test_reject_stage_reordering_and_privileged_fields(self):
        rows = self.make_export()
        bad = copy.deepcopy(rows)
        bad[1]["index"] = 3
        with self.assertRaises(DataError):
            validate_rows(bad)
        rows[0]["env_point_cloud"] = []
        with self.assertRaisesRegex(DataError, "source"):
            validate_rows(rows)

    def test_corrupt_rgb_hash_refused(self):
        self.make_export()
        image = self.output / "rgb/stage_1-000000.npy"
        image.write_bytes(b"corrupt")
        with self.assertRaisesRegex(DataError, "RGB hash"):
            load_export(self.output)

    def test_missing_completion_manifest_refused(self):
        self.output.mkdir()
        with self.assertRaises(FileNotFoundError):
            load_export(self.output)

    def test_nonfinite_input_before_output(self):
        import numpy as np
        record = {"joint_state": np.full(60, float("nan")), "image": np.zeros((2, 2, 3), dtype=np.uint8)}
        np.savez(self.source, **{s: np.array([record], dtype=object) for s in ("stage_1", "stage_2", "stage_3")})
        with self.assertRaisesRegex(ValueError, "finite"):
            export(self.source, self.output, digest(self.source), trusted=True)
        self.assertFalse(self.output.exists())


class SubmittedHandoffTests(unittest.TestCase):
    def test_real_submitted_json_and_inventory(self):
        result = audit(Path(__file__).resolve().parents[1])
        self.assertEqual(result["submitted_observation"]["joint_values"], 60)
        self.assertEqual(len(result["verified_repo_artifacts"]), 2)
        self.assertFalse(result["raw_npz_independently_verified"])
        self.assertFalse(result["h1_h2_evidence"])


if __name__ == "__main__":
    unittest.main()
