import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class AssetVerifierTest(unittest.TestCase):
    def test_matching_modified_and_missing_asset(self):
        script = Path(__file__).resolve().parents[1] / 'tools' / 'simulation' / 'verify_demo_assets.py'
        with tempfile.TemporaryDirectory(prefix='assets-test-') as tmp:
            root = Path(tmp)
            asset = root / 'Assets' / 'demo' / 'cloth.bin'
            asset.parent.mkdir(parents=True)
            asset.write_bytes(b'cloth')
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps({'schema_version': 'asset-fingerprints/1', 'files': [
                {'path': 'demo/cloth.bin', 'size_bytes': 5, 'sha256': hashlib.sha256(b'cloth').hexdigest()}
            ]}), encoding='utf-8')
            command = [sys.executable, str(script), '--project-root', str(root), '--manifest', str(manifest)]
            def run():
                return subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(run().returncode, 0)
            asset.write_bytes(b'wrong')
            changed = run()
            self.assertNotEqual(changed.returncode, 0)
            self.assertIn('sha256 mismatch', changed.stdout)
            asset.unlink()
            missing = run()
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn('missing or unsafe', missing.stdout)


if __name__ == '__main__':
    unittest.main()
