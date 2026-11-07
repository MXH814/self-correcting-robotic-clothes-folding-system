"""Export one numeric observation from a specifically trusted NPZ, never an arbitrary pickle.

The SHA-256 check identifies the archive but cannot make an untrusted pickle safe.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--sha256', required=True, help='Expected SHA-256 obtained through a trusted channel')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--stage', choices=('stage_1', 'stage_2', 'stage_3'), default='stage_1')
    parser.add_argument('--index', type=int, default=0)
    args = parser.parse_args()
    digest = hashlib.sha256()
    with args.input.open('rb') as source:
        for block in iter(lambda: source.read(4 * 1024 * 1024), b''):
            digest.update(block)
    actual = digest.hexdigest()
    if actual.lower() != args.sha256.lower():
        raise ValueError('Source hash mismatch; refusing to deserialize')
    # Only use this for a source the operator independently trusts: object arrays use pickle.
    with np.load(args.input, allow_pickle=True) as archive:
        record = archive[args.stage][args.index]
        fields = {}
        for key, value in record.items():
            array = np.asarray(value)
            fields[key] = {'shape': list(array.shape), 'dtype': str(array.dtype)}
        sample = {
            'source_sha256': actual,
            'stage': args.stage,
            'index': args.index,
            'timestamps': 'not recorded',
            'fields': fields,
            'joint_state': np.asarray(record['joint_state']).tolist(),
            'joint_state_order': 'left articulation 30 values followed by right articulation 30 values; name-index mapping unverified',
            'action': None,
            'action_note': 'NPZ frame does not record a dispatched command or acknowledgment',
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as output:
        json.dump(sample, output, indent=2, ensure_ascii=False, allow_nan=False)
        output.write('\n')
    print('Exported:', args.output)


if __name__ == '__main__':
    main()
