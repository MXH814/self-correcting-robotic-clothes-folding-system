import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
from research_tools.dex_dataset import inspect_npz
from research_tools.diagnostics import DataError, evaluate, forward_stage_score, synthetic


def npy_header(descr="<f4", shape=(3,)):
    h = repr({"descr": descr, "shape": shape, "fortran_order": False}).encode("ascii") + b"\n"
    return b"\x93NUMPY\x01\x00" + struct.pack("<H", len(h)) + h


class DatasetTests(unittest.TestCase):
    def test_headers_without_payload(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "fixture.npz"
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("joint_state.npy", npy_header())
                z.writestr("stage1.npy", npy_header("|O", ()))
            before = path.read_bytes()
            r = inspect_npz(path)
            self.assertFalse(r["pickle_loaded"])
            self.assertFalse(r["trajectory_validated"])
            self.assertTrue(r["arrays"][1]["object_payload"])
            self.assertEqual(path.read_bytes(), before)

    def test_bad_archive_member(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "bad.npz"
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("payload.py", "raise RuntimeError()")
            with self.assertRaises(DataError):
                inspect_npz(path)

    def test_expansion_limit(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "large.npz"
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("a.npy", npy_header())
            with self.assertRaises(DataError):
                inspect_npz(path, max_uncompressed=1)

    def test_header_length_limit(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "header.npz"
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("a.npy", b"\x93NUMPY\x02\x00" + struct.pack("<I", 1000000))
            with self.assertRaises(DataError):
                inspect_npz(path)

    def test_forward_proxy_is_not_probability(self):
        self.assertEqual(forward_stage_score(3., 2.), -2.)
        self.assertIsNone(forward_stage_score(3., 4.))
        with self.assertRaises(DataError):
            forward_stage_score(-1., 0.)

    def test_optional_stage_baseline(self):
        rows = synthetic()
        for r in rows:
            r["stage_cost_score"] = -float(r["candidate_id"])
        result = evaluate(rows)
        self.assertIn("stage_cost", result["summary"])
        self.assertIn("stage_cost_vs_B1", result["paired"])
        del rows[0]["stage_cost_score"]
        with self.assertRaises(DataError):
            evaluate(rows)


if __name__ == "__main__":
    unittest.main()
