"""Read-only verification of author-machine Fold Tops asset fingerprints."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args()
    root = (args.project_root / 'Assets').resolve()
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    if manifest.get('schema_version') != 'asset-fingerprints/1':
        raise ValueError('unknown manifest version')
    bad = []
    for item in manifest['files']:
        name = PurePosixPath(item['path'])
        if name.is_absolute() or '..' in name.parts or not name.parts:
            raise ValueError('unsafe asset path')
        p = (root / Path(*name.parts)).resolve()
        if not p.is_relative_to(root) or not p.is_file():
            bad.append((str(name), 'missing or unsafe'))
            continue
        if p.stat().st_size != item['size_bytes']:
            bad.append((str(name), 'size mismatch'))
            continue
        h = hashlib.sha256()
        with p.open('rb') as f:
            for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
                h.update(block)
        if h.hexdigest() != item['sha256']:
            bad.append((str(name), 'sha256 mismatch'))
    for name, reason in bad:
        print(reason + ': ' + name)
    print(f'Checked {len(manifest["files"])} assets; mismatches={len(bad)}')
    if bad:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
