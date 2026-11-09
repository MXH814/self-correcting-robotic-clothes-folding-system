"""Recompute recorded model decisions from shared RGB, not online latency.

The main detection events and the additional preflight refresh are replayed in
capture order. Identity, phase, generation, threshold, status and reason remain
exact. Only model scores allow an explicit absolute cross-platform tolerance.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from research_tools.detection_encoder import FrozenRGBEncoder, file_hash
from research_tools.garment_trace_intake import verify_files, validate_trace
from research_tools.observation_detector import OnlineObservationDetector, load_package


def lines(path):
    return [json.loads(line) for line in path.read_text(encoding='utf8').splitlines()]


def replay(root, package, encoder_weights, *, score_atol=1e-5):
    import torch
    torch.set_num_threads(4)
    assert 0 < score_atol <= 1e-5
    verify_files(root)
    trace = json.loads((root / 'observation-trace.json').read_bytes())
    with np.load(root / 'rgb-frames.npz', allow_pickle=False) as archive:
        rgb = archive['rgb']
    validate_trace(trace, rgb)
    events = lines(root / 'pre-demo-events.jsonl')
    journal = lines(root / 'official-workflow-events.jsonl')
    calls = [{'metadata': event['observation'], 'recorded': event['report'], 'kind': 'main'}
             for event in events if event['kind'] == 'OFFICIAL_DETECTION']
    # Refresh reports have no repeated embedding; reconstruct metadata only
    # from their bound source observation and the already-declared hold phase.
    observations = {row['observation_id']: row for row in trace['observations']}
    manifest = json.loads((package / 'manifest.json').read_bytes())
    for event in journal:
        if event.get('kind') == 'PREFLIGHT_DETECTION_REFRESHED':
            report = event['report']
            obs = observations[report['observation_id']]
            calls.append({'kind': 'preflight-refresh', 'recorded': report, 'metadata': {
                'trial_id': trace['trial_id'], 'lineage_group': trace['trial_id'],
                'observation_id': obs['observation_id'], 'frame_id': str(obs['rendering_frame']),
                'sim_time_s': obs['rendering_time_s'],
                'read_sim_time_s': obs['camera_read_end']['sim_time_s'],
                'phase': 'LEFT_SLEEVE_HOLD', 'context_reference': manifest['context_reference'],
                'encoder_reference': manifest['encoder_reference']}})
    calls.sort(key=lambda item: item['recorded']['captured_wall_s'])
    encoder = FrozenRGBEncoder(encoder_weights)
    model, meta = load_package(package, encoder_reference=encoder.reference,
                               context_reference=manifest['context_reference'])
    detector = OnlineObservationDetector(model, meta)
    maximum = {'raw_score': 0., 'score': 0.}
    mismatch = []
    kinds = Counter()
    exact_fields = ('trial_id', 'observation_id', 'generation', 'package_id',
                    'context_reference', 'threshold', 'status', 'reason', 'observed_sim_s')
    scores = []
    # Batch one preserves the recorded CPU inference call's numerical path.
    for index, item in enumerate(calls):
        metadata, recorded = item['metadata'], item['recorded']
        obs = observations[metadata['observation_id']]
        assert metadata['trial_id'] == trace['trial_id'] == recorded['trial_id']
        assert metadata['frame_id'] == str(obs['rendering_frame'])
        embedding = encoder.encode([rgb[obs['frame_index']]])[0].tolist()
        row = dict(metadata, embedding=embedding)
        reproduced = detector.detect(row, generation=recorded['generation'],
            captured_wall_s=recorded['captured_wall_s'], now_wall_s=recorded['captured_wall_s'])
        kinds[item['kind']] += 1
        for field in exact_fields:
            if reproduced.get(field) != recorded.get(field):
                mismatch.append({'call': index, 'field': field, 'recorded': recorded.get(field),
                                 'reproduced': reproduced.get(field)})
        for field in maximum:
            actual, expected = reproduced[field], recorded[field]
            if actual is None or expected is None:
                if actual != expected:
                    mismatch.append({'call': index, 'field': field, 'reason': 'null mismatch'})
            else:
                difference = abs(actual - expected)
                maximum[field] = max(maximum[field], difference)
                if not np.isfinite(difference) or difference > score_atol:
                    mismatch.append({'call': index, 'field': field, 'difference': difference})
        scores.append({'observation_id': metadata['observation_id'], 'kind': item['kind'],
                       'status': reproduced['status'], 'raw_score': reproduced['raw_score'],
                       'score': reproduced['score']})
        if (index + 1) % 100 == 0:
            print(f'Recomputed {index + 1}/{len(calls)}', flush=True)
    return {'schema': 'pre-rgb-detector-independent-replay/1', 'trial_id': trace['trial_id'],
            'package_id': meta['package_id'], 'checkpoint_sha256': file_hash(package / 'detector.pt'),
            'rgb_sha256': file_hash(root / 'rgb-frames.npz'),
            'trace_sha256': file_hash(root / 'observation-trace.json'),
            'events_sha256': file_hash(root / 'pre-demo-events.jsonl'),
            'calls': dict(kinds), 'max_score_abs_delta': maximum, 'score_atol': score_atol,
            'exact_field_mismatch_count': len(mismatch), 'mismatches': mismatch,
            'all_recorded_decisions_reproduced': not mismatch,
            'replay_only': True, 'online_latency_reproduced': False,
            'scores': scores}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--encoder-weights', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = replay(args.root, args.package, args.encoder_weights)
    with args.output.open('x', encoding='utf8') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps({key: value for key, value in result.items() if key != 'scores'}, indent=2))
    raise SystemExit(0 if result['all_recorded_decisions_reproduced'] else 1)
