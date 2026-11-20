"""Export the five-screen UI and the records referenced by its replay pages."""
import argparse
from html.parser import HTMLParser
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


class ReplayAssets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = set()

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in ("href", "src") and value:
                self.paths.add(value)


def export(output):
    repo = Path(__file__).resolve().parents[2]
    ui = repo / "prototypes/ui"
    records = repo / "docs/research/zhangmingbo"
    z3 = Path("pre-abc-evidence-20261109/Z3")
    parser = ReplayAssets()
    parser.feed((records / z3 / "index.html").read_text(encoding="utf-8"))
    assets = {z3 / "index.html", *(z3 / p for p in parser.paths)}
    assets.update(Path("fold-experiments-20261108") / (name + ".png")
                  for name in ("stage-1", "stage-2", "stage-3", "final"))
    assets.update(map(Path, ("fold-experiments-20261108.md", "adapter-fault-probe-20261108.md")))
    with ZipFile(output, "x", ZIP_DEFLATED) as archive:
        for path in sorted(ui.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            name = path.relative_to(ui)
            data = path.read_bytes()
            if name.as_posix() in ("replay/index.html", "replay/detection.html", "replay/replay.js"):
                data = data.replace(b"../../../docs/research/zhangmingbo/", b"records/")
            archive.writestr((Path("prototype") / name).as_posix(), data)
        for name in sorted(assets):
            archive.write(records / name, Path("prototype/replay/records") / name)


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("output", type=Path, help="Path to a new .zip file")
    export(cli.parse_args().output)
