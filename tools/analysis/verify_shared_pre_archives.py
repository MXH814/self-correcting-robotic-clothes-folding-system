"""Verify the complete shared archive, then extract into fresh isolated folders."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def verify(manifest_path, archives, output, only=None):
    manifest = json.loads(manifest_path.read_bytes())
    result = {'schema': 'shared-pre-archive-audit/1',
              'manifest_sha256': sha(manifest_path), 'package_id': manifest['package_id'],
              'archives': []}
    entries = manifest['archives']
    if only:
        assert set(only) <= {entry['file'] for entry in entries}, 'Unknown archive name'
        entries = [entry for entry in entries if entry['file'] in set(only)]
    result['coverage'] = 'all' if len(entries) == len(manifest['archives']) else 'selected'
    if output.exists():
        raise ValueError('Extraction destination must be new')
    for entry in entries:
        archive = archives / entry['file']
        assert archive.stat().st_size == entry['bytes'], entry['file']
        assert sha(archive) == entry['sha256'], entry['file']
        with zipfile.ZipFile(archive) as zipped:
            prefix = Path(entry['file']).stem + '/'
            expected = {prefix + row['path']: row for row in entry['files']}
            assert len(expected) == len(entry['files'])
            members = [item for item in zipped.infolist() if not item.is_dir()]
            assert len(members) == len(expected)
            assert {item.filename for item in members} == set(expected)
            for item in members:
                relative = PurePosixPath(item.filename)
                assert not relative.is_absolute() and '..' not in relative.parts
                assert '\\' not in item.filename and ':' not in item.filename
                assert item.file_size == expected[item.filename]['bytes']
                digest = hashlib.sha256()
                with zipped.open(item) as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                        digest.update(chunk)
                assert digest.hexdigest() == expected[item.filename]['sha256']
            result['archives'].append({'file': entry['file'], 'bytes': entry['bytes'],
                                       'sha256': entry['sha256'], 'verified_files': len(members)})
    # Nothing is extracted until every archive and member has passed.
    output.mkdir(parents=True)
    for entry in entries:
        with zipfile.ZipFile(archives / entry['file']) as zipped:
            zipped.extractall(output)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('archives', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--only', action='append', help='Verify and extract only these named archives')
    args = parser.parse_args()
    result = verify(args.manifest, args.archives, args.output, args.only)
    with args.report.open('x', encoding='utf8') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps(result, indent=2))
