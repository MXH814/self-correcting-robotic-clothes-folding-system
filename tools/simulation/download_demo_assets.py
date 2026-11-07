"""Fetch official robot assets and only the garment/scene needed by Fold_Tops."""
import io
import http.client
import json
import os
from pathlib import Path
import urllib.request
import zipfile
import time

ROOT = Path(os.environ["ROBOTICS_PROJECT_ROOT"]).resolve()
ASSETS = ROOT / "Assets"
BASE = "https://huggingface.co/datasets/wayrise/DexGarmentLab/resolve/main/"


class RemoteZip(io.RawIOBase):
    def __init__(self, url):
        self.url = url
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=60) as response:
            self.size = int(response.headers["Content-Length"])
        self.pos = 0
        self.cache_start = 0
        self.cache = b""

    def seekable(self):
        return True

    def seek(self, offset, whence=0):
        self.pos = offset if whence == 0 else self.pos + offset if whence == 1 else self.size + offset
        return self.pos

    def tell(self):
        return self.pos

    def read(self, count=-1):
        if count < 0:
            count = self.size - self.pos
        count = min(count, self.size - self.pos)
        if count <= 0:
            return b""
        if not (self.cache_start <= self.pos and self.pos + count <= self.cache_start + len(self.cache)):
            end = min(self.size, self.pos + max(count, 1024 * 1024)) - 1
            data = b""
            for attempt in range(10):
                start = self.pos + len(data)
                if start > end:
                    break
                request = urllib.request.Request(self.url, headers={"Range": f"bytes={start}-{end}"})
                try:
                    with urllib.request.urlopen(request, timeout=60) as response:
                        if response.status != 206:
                            raise RuntimeError("Server does not support range reads")
                        expected = f"bytes {start}-{end}/{self.size}"
                        if response.headers.get("Content-Range") != expected:
                            raise RuntimeError("Wrong range response")
                        try:
                            data += response.read()
                        except http.client.IncompleteRead as exc:
                            data += exc.partial
                except Exception as exc:
                    if attempt == 9:
                        raise
                    print("Retry asset range:", exc, flush=True)
                    time.sleep(2)
            if len(data) != end - self.pos + 1:
                raise RuntimeError("Incomplete range response after retries")
            self.cache_start, self.cache = self.pos, data
        offset = self.pos - self.cache_start
        data = self.cache[offset:offset + count]
        self.pos += len(data)
        return data


def extract_selected(archive, select):
    with zipfile.ZipFile(RemoteZip(BASE + archive + "?download=true")) as source:
        files = [entry for entry in source.infolist() if not entry.is_dir() and select(entry.filename)]
        if not files:
            raise RuntimeError("No required files found in " + archive)
        print(archive, len(files), "files,", sum(entry.file_size for entry in files), "bytes", flush=True)
        for entry in files:
            target = (ASSETS / entry.filename).resolve()
            if not target.is_relative_to(ASSETS.resolve()):
                raise RuntimeError("Unsafe archive entry")
            if target.exists():
                if target.stat().st_size == entry.file_size:
                    continue  # Same size is not a cryptographic integrity check.
                raise RuntimeError(f"Existing file has a different size; refusing overwrite: {target}")
            target.parent.mkdir(parents=True, exist_ok=True)
            data = source.read(entry)  # ZIP CRC is checked by zipfile.
            with target.open("xb") as output:
                output.write(data)
            print("Saved", entry.filename, flush=True)
        return [entry.filename for entry in files]


def main():
    output = ROOT / "local-demo-assets.json"
    if output.exists():
        raise RuntimeError(f"Manifest already exists; refusing overwrite: {output}")
    ASSETS.mkdir(parents=True, exist_ok=True)
    manifest = {}
    manifest["Garment.zip"] = extract_selected("Garment.zip", lambda name: "/TCLC_018/" in name)
    manifest["Robots.zip"] = extract_selected("Robots.zip", lambda name: True)
    manifest["Scene.zip"] = extract_selected("Scene.zip", lambda name: name.startswith("Scene/Collected_default_environment/"))
    output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("Required demo assets are ready.", flush=True)


if __name__ == "__main__":
    main()
