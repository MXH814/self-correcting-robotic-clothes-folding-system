"""Software fixtures only; these tests do not assert robot recovery performance."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from research_tools.diagnostics import DataError, validate
from research_tools.legacy_features import encode_export, export_features, rgb_grid
from research_tools.legacy_observations import digest
from tools.simulation.export_numeric_trajectory import export


@unittest.skipUnless(importlib.util.find_spec("numpy"), "NumPy optional")
class FeatureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def make_export(self, name="base", future_value=90):
        import numpy as np
        source = self.root / (name + ".npz")
        rows = np.array([{"joint_state": np.arange(60, dtype=np.float32) + i,
                          "image": np.full((4, 4, 3), value, dtype=np.uint8)}
                         for i, value in enumerate((10, 20, future_value))], dtype=object)
        np.savez(source, **{stage: rows for stage in ("stage_1", "stage_2", "stage_3")})
        dest = self.root / name
        export(source, dest, digest(source), trusted=True)
        return dest

    def test_spatial_color_order_and_scale(self):
        import numpy as np
        image = np.zeros((4, 4, 3), dtype=np.uint8)
        image[:2, :2] = [255, 0, 0]
        image[:2, 2:] = [0, 255, 0]
        image[2:, :2] = [0, 0, 255]
        image[2:, 2:] = [255, 255, 255]
        self.assertEqual(rgb_grid(image, 2), [1., 0., 0., 0., 1., 0., 0., 0., 1., 1., 1., 1.])
        with self.assertRaises(DataError):
            rgb_grid(image, 5)

    def test_future_change_cannot_change_earlier_features(self):
        first, _ = encode_export(self.make_export("first", 90), grid=2, history=2)
        changed, _ = encode_export(self.make_export("changed", 230), grid=2, history=2)
        for index in (0, 1):
            for field in ("current_rgb", "joint_raw", "past_rgb", "past_joint_raw", "history_mask"):
                self.assertEqual(first[index][field], changed[index][field])
        self.assertNotEqual(first[2]["current_rgb"], changed[2]["current_rgb"])

    def test_stage_boundary_and_unknown_actions_remain_explicit(self):
        rows, _ = encode_export(self.make_export(), grid=2, history=2)
        self.assertEqual(rows[2]["history_mask"], [True, True])
        self.assertEqual(rows[3]["history_mask"], [False, False])
        self.assertEqual(rows[3]["past_rgb"], [0.] * 24)
        self.assertNotIn(rows[2]["frame_id"], rows[2]["past_frame_ids"])
        for row in rows:
            self.assertIsNone(row["action_history"])
            self.assertIsNone(row["sim_time_s"])
            self.assertIsNone(row["autonomous_success"])
            self.assertFalse(row["online_authorized"])
        with self.assertRaises(DataError):
            validate(rows)

    def test_corruption_rejected_before_output_creation(self):
        source = self.make_export()
        (source / "rgb/stage_1-000000.npy").write_bytes(b"corrupt")
        dest = self.root / "features"
        with self.assertRaisesRegex(DataError, "RGB hash"):
            export_features([source], dest, grid=2)
        self.assertFalse(dest.exists())

    def test_no_overwrite_and_manifest_binds_records(self):
        source = self.make_export()
        dest = self.root / "features"
        result = export_features([source], dest, grid=2)
        self.assertEqual(result["frames"], 9)
        self.assertEqual(result["features_sha256"], digest(dest / "features.jsonl"))
        self.assertFalse(result["train_validation_split_created"])
        original = (dest / "manifest.json").read_bytes()
        with self.assertRaises(FileExistsError):
            export_features([source], dest, grid=2)
        self.assertEqual(original, (dest / "manifest.json").read_bytes())
        self.assertEqual(json.loads(original)["encoder"]["fitted_parameters"], 0)

    def test_duplicate_source_and_input_output_overlap_rejected(self):
        source = self.make_export()
        dest = self.root / "features"
        with self.assertRaisesRegex(DataError, "duplicate"):
            export_features([source, source], dest, grid=2)
        self.assertFalse(dest.exists())
        with self.assertRaisesRegex(DataError, "outside"):
            export_features([source], source / "features", grid=2)


if __name__ == "__main__":
    unittest.main()
