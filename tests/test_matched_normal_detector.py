"""Regression coverage for binding independent normal review to the original bytes."""
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from research_tools import matched_normal_detector as detector


class MatchedSourceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        reviews = {}
        for folder, uid, role in detector.TRIALS:
            raw = self.root / folder / "raw"
            raw.mkdir(parents=True)
            self.write_trial(raw, uid, b"reviewed frame")
            reviews[uid] = dict(folder=folder, role=role,
                                source_reference="manifest#sha256=" + detector.file_hash(raw / "manifest.json"))
        self.review = self.root / "fixed-review.json"
        self.review.write_text(json.dumps(reviews), encoding="utf8")
        patcher = patch.object(detector, "REVIEW", self.review)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write_trial(self, raw, uid, data):
        (raw / "frame.bin").write_bytes(data)
        manifest = {"trial_id": uid, "files": [{"file": "frame.bin", "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest()}]}
        (raw / "manifest.json").write_text(json.dumps(manifest), encoding="utf8")

    def test_reviewed_inputs_and_assignments(self):
        for folder, uid, role in detector.TRIALS:
            raw = self.root / folder / "raw"
            self.assertEqual(detector.reviewed_source(raw, folder, uid, role),
                             detector.read(self.review)[uid]["source_reference"])
            with self.assertRaisesRegex(ValueError, "review required"):
                detector.reviewed_source(raw, folder, uid, "unreviewed-role")

    def test_rebuilt_manifest_rejected_before_first_trial(self):
        folder, uid, role = detector.TRIALS[-1]
        raw = self.root / folder / "raw"
        self.write_trial(raw, uid, b"replacement frame")
        # Even a plausible current-run review must not override the fixed baseline.
        forged = detector.read(self.review)
        forged[uid]["source_reference"] = "manifest#sha256=" + detector.file_hash(raw / "manifest.json")
        (self.root / "review.json").write_text(json.dumps(forged), encoding="utf8")
        with patch.object(detector, "prepare") as prepare, patch.object(detector, "fit") as fit:
            with self.assertRaisesRegex(ValueError, "review required"):
                detector.run(self.root, None, self.root)
            prepare.assert_not_called()
            fit.assert_not_called()
        with patch.object(detector.np, "load") as load, patch.object(detector, "export_trace") as encode:
            with self.assertRaisesRegex(ValueError, "review required"):
                detector.prepare(raw, None, self.root, folder, uid)
            load.assert_not_called()
            encode.assert_not_called()
