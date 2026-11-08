"""用法：python import_recordings.py <存放两个 Release ZIP 的目录>。需要 Pillow 和 NumPy。"""
import argparse
import hashlib
import io
import json
from tempfile import NamedTemporaryFile
import zipfile
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image

OUTPUT = Path(__file__).resolve().parent
ARCHIVES = {
    "data2": "6584a58167d25bef6da25eecdaf8436df8b93b1ad9cea6d8fe01f9fb70986a16",
    "data3": "4808365cf9caf7454bec5ef3ca1a077bed86e7f6c8d1e5b20b7f9ccbb288cfa9",
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify(condition, field):
    if not condition:
        raise ValueError(f"数据核对失败：{field}")


def publish(path, content):
    temp = NamedTemporaryFile(dir=path.parent, delete=False)
    pending = Path(temp.name)
    try:
        with temp:
            temp.write(content)
        pending.replace(path)
    finally:
        pending.unlink(missing_ok=True)


def convert(name, directory):
    path = directory / (name + ".zip")
    if not path.is_file():
        filename = {"data2":"fold-tops-data2-numeric-20261107.zip", "data3":"fold-tops-data3-evidence-20261108.zip"}[name]
        path = directory / filename
        if not path.is_file():
            raise FileNotFoundError(f"{directory} 中缺少 {filename}（也可命名为 {name}.zip）")
    verify(digest(path.read_bytes()) == ARCHIVES[name], name)
    target = OUTPUT / "frames" / name
    target.mkdir(exist_ok=True, parents=True)
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        raw = archive.read("observations.jsonl")
        verify(digest(raw) == manifest["records_sha256"], "records")
        records = [json.loads(line) for line in raw.splitlines()]
        verify(len(records) == manifest["frames"], "frames")
        counts = Counter()
        for ordinal, row in enumerate(records):
            stage = row["stage"]
            verify(row["trajectory_id"] == manifest["source_sha256"], "trajectory")
            verify(row["index"] == counts[stage], "index")
            counts[stage] += 1
            joints = np.asarray(row["joint_state"])
            verify(joints.shape == (60,) and np.isfinite(joints).all(), "joint_state")
            rgb = row["rgb"]
            data = archive.read(rgb["path"])
            verify(digest(data) == rgb["sha256"], rgb["path"])
            pixels = np.load(io.BytesIO(data), allow_pickle=False)
            verify(pixels.shape == (480, 640, 3) and pixels.dtype == np.uint8, "RGB")
            image_path = target / f"{ordinal:03d}.png"
            encoded = io.BytesIO()
            Image.fromarray(pixels).save(encoded, format="PNG", compress_level=3)
            encoded.seek(0)
            with Image.open(encoded) as png:
                verify(np.array_equal(np.asarray(png), pixels), "PNG 像素")
            publish(image_path, encoded.getvalue())
        verify(counts == manifest["stage_counts"], "stages")
    return {"manifest": manifest, "records": records, "archive_sha256": ARCHIVES[name]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="包含两个已下载 ZIP 的目录")
    args = parser.parse_args()
    try:
        data = {name: convert(name, args.directory) for name in ARCHIVES}
    except FileNotFoundError as error:
        parser.exit(1, f"{error}\n")
    script = "const trajectories = " + json.dumps(data, separators=(",", ":")) + ";\n"
    publish(OUTPUT / "records.js", script.encode("utf8"))
    for name, entry in data.items():
        print(name, len(entry["records"]), "frames verified")
