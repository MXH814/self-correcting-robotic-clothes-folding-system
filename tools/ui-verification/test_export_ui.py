"""Regression check for the evidence links in the standalone ZIP."""
import re
import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote, urlsplit
from zipfile import ZipFile

from export_ui import export


class OfflineEvidenceTest(unittest.TestCase):
    def test_experiment_notes_resolve_in_extracted_zip(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "ui.zip"
            export(archive)
            with ZipFile(archive) as package:
                package.extractall(root)
            records = root / "prototype/replay/records"
            for name in ("fold-experiments-20261108.md", "adapter-fault-probe-20261108.md"):
                self.assertTrue((records / name).is_file(), name)
            for note in records.rglob("*.md"):
                for href in re.findall(r"\]\(([^)]+)\)", note.read_text(encoding="utf-8")):
                    url = urlsplit(href)
                    if not url.scheme and not url.netloc and url.path:
                        with self.subTest(note=note.name, link=href):
                            target = (note.parent / unquote(url.path)).resolve()
                            self.assertTrue(target.is_relative_to(root) and target.is_file())


if __name__ == "__main__":
    unittest.main()
