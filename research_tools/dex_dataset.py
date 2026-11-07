"""Read-only NPZ header inventory. Never unpickles arrays or executes simulator code."""
import argparse
import ast
import hashlib
import json
import math
import re
import struct
import zipfile
from pathlib import Path
from .diagnostics import require


def object_descriptor(value):
    if isinstance(value, str):
        return bool(re.fullmatch(r"[<>=|]?O\d*", value))
    if isinstance(value, (list, tuple)):
        return any(object_descriptor(x) for x in value)
    return False


def inspect_npz(path, max_uncompressed=2 * 1024**3):
    path = Path(path)
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    arrays = []
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        require(len(infos) <= 10000, "too many archive members")
        require(len({i.filename for i in infos}) == len(infos), "duplicate archive member")
        require(sum(i.file_size for i in infos) <= max_uncompressed, "declared archive expansion exceeds limit")
        for info in infos:
            require(info.filename.endswith(".npy"), "not an array-only NPZ")
            with archive.open(info) as f:
                require(f.read(6) == b"\x93NUMPY", "invalid NPY magic")
                version = tuple(f.read(2))
                require(version in ((1, 0), (2, 0), (3, 0)), "unsupported NPY version")
                size = 2 if version == (1, 0) else 4
                length_bytes = f.read(size)
                require(len(length_bytes) == size, "truncated header size")
                n = struct.unpack("<H" if size == 2 else "<I", length_bytes)[0]
                require(n <= 65536, "NPY header too large")
                raw = f.read(n)
                require(len(raw) == n, "truncated header")
                header = ast.literal_eval(raw.decode("utf-8" if version == (3, 0) else "latin1"))
                require(isinstance(header, dict) and set(header) == {"descr", "shape", "fortran_order"},
                        "unexpected header schema")
                shape = header["shape"]
                require(isinstance(shape, tuple) and all(type(x) is int and x >= 0 for x in shape), "invalid shape")
                arrays.append({"key": info.filename[:-4], "shape": list(shape),
                               "element_count": math.prod(shape), "dtype_descriptor": header["descr"],
                               "object_payload": object_descriptor(header["descr"]),
                               "declared_uncompressed_bytes": info.file_size,
                               "payload_read": False})
    return {"schema": "dex-npz-header-audit/1", "input_file": path.name,
            "input_sha256": digest.hexdigest(), "file_bytes": path.stat().st_size,
            "arrays": arrays, "pickle_loaded": False, "trajectory_validated": False,
            "online_provenance_validated": False, "quality_evaluated": False,
            "note": "Headers only. Object-array nested fields, timestamps, values, asset existence, CRC of full payload, contact/quality and source provenance remain unverified. No extraction or writes to input."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = inspect_npz(args.input)
    with Path(args.output).open("x", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, allow_nan=False)


if __name__ == "__main__":
    main()
