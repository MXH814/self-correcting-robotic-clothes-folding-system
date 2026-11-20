"""Export the five-screen UI and the records referenced by its replay pages."""
import argparse
import re
from urllib.parse import urlsplit, unquote
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


# The experiment notes use inline Markdown links. Keep their record files offline.
INLINE_LINK = re.compile(r"\[([^]\n]*)\]\(([^)\s]+)\)")
SOURCE_URL = "https://github.com/MXH814/self-correcting-robotic-clothes-folding-system/blob/fa2824f8c287f2252067d12444430a4b1bf047c5/"


def experiment_materials(repo, records):
    pending = [records / name for name in (
        "fold-experiments-20261108.md", "adapter-fault-probe-20261108.md")]
    files = {}
    while pending:
        source = pending.pop()
        if source in files:
            continue
        data = source.read_bytes()
        if source.suffix == ".md":
            def local_reference(match):
                label, href = match.groups()
                url = urlsplit(href)
                if url.scheme or url.netloc or not url.path:
                    return match.group()
                target = (source.parent / unquote(url.path)).resolve(strict=True)
                if target.is_relative_to(records):
                    pending.append(target)
                    return match.group()
                # Installation notes also cite project-wide configuration and plans.
                relative = target.relative_to(repo).as_posix()
                return f"[{label}（需联网访问仓库）]({SOURCE_URL}{relative})"

            data = INLINE_LINK.sub(local_reference, data.decode("utf-8")).encode("utf-8")
        files[source] = data
    return files


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
    materials = experiment_materials(repo, records)
    assets.difference_update(source.relative_to(records) for source in materials)
    with ZipFile(output, "x", ZIP_DEFLATED) as archive:
        for path in sorted(ui.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            name = path.relative_to(ui)
            data = path.read_bytes()
            if name.as_posix() in ("replay/index.html", "replay/detection.html", "replay/replay.js"):
                data = data.replace(b"../../../docs/research/zhangmingbo/", b"records/")
            archive.writestr((Path("prototype") / name).as_posix(), data)
        for source, data in sorted(materials.items()):
            archive.writestr((Path("prototype/replay/records") / source.relative_to(records)).as_posix(), data)
        for name in sorted(assets):
            archive.write(records / name, Path("prototype/replay/records") / name)


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("output", type=Path, help="Path to a new .zip file")
    export(cli.parse_args().output)
