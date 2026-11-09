"""Check the distinct report, request, attempt, operation and SDK record layers.

Reads the frozen portable A/B/C evidence only. Counts are evidence properties,
not independent robot trials, calibrated accuracy or product acceptance.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def summarize(root):
    manifest = json.loads((root / 'portable-manifest.json').read_bytes())
    inventory = {row['file']: row for row in manifest['files']}
    sources, cases = {}, {}

    def read(relative, jsonl=False):
        content = (root / relative).read_bytes()
        expected = inventory[relative]
        digest = hashlib.sha256(content).hexdigest()
        if len(content) != expected['bytes'] or digest != expected['sha256']:
            raise ValueError('Evidence inventory mismatch: ' + relative)
        sources[relative] = digest
        if jsonl:
            return [json.loads(line) for line in content.decode('utf8').splitlines()]
        return json.loads(content)

    for case in ('A', 'B', 'C'):
        events = read(case + '/pre-demo-events.jsonl', True)
        journal = read(case + '/official-workflow-events.jsonl', True)
        record = read(case + '/full-fold-recovery.json')
        trace = read(case + '/observation-trace.json')
        trial = record['trial_id']
        assert trace['trial_id'] == trial
        assert all(row['trial_id'] == trial for row in events + journal)
        reports = [row for row in events if row['kind'] == 'OFFICIAL_DETECTION']
        assert len({row['observation']['observation_id'] for row in reports}) == len(reports)
        requests = [row for row in journal if row.get('kind') == 'REQUEST_RECOVERY_PREFLIGHT']
        accepted = [row for row in journal if row.get('kind') == 'MACRO_ACCEPTED']
        refreshed = [row for row in journal if row.get('kind') == 'PREFLIGHT_DETECTION_REFRESHED']
        repeated_refresh = [row for row in events if row['kind'] == 'PREFLIGHT_REDETECTION']
        assert len(repeated_refresh) == len(refreshed)
        for primary, repeated in zip(refreshed, repeated_refresh):
            assert primary['report'] == repeated['report']
            assert primary['request_id'] == repeated['request']['request_id']
            assert primary['request_id'] in {row['request_id'] for row in requests}
        assert len({row['request_id'] for row in requests}) == len(requests)
        assert len(accepted) == record.get('recovery_attempts', 0)
        # MACRO_ACCEPTED is persisted before attempts increments. Its explicit
        # accepted_attempt_no is the allocation, not the event's old snapshot.
        assert [row['accepted_attempt_no'] for row in accepted] == list(range(1, len(accepted) + 1))
        assert all(row['request_id'] in {x['request_id'] for x in requests} for row in accepted)
        operations = record.get('macro_execution', [])
        commands = [command for operation in operations for command in operation['command_ids']]
        assert len(commands) == len(set(commands))
        dispatch = {row['command_id']: row for row in trace['actions']}
        assert len(dispatch) == len(trace['actions'])
        assert set(commands) <= set(dispatch)
        if accepted:
            assert len(accepted) == 1  # Scope: this frozen diagnostic, not all future runs.
            assert [row['operation'] for row in operations] == accepted[0]['operations']
        else:
            assert not operations and not commands
        checks = [row for row in events if row['kind'] == 'RECOVERY_CHECK']
        baseline = [row for row in events if row['kind'] == 'CONTINUATION_BASELINE']
        continuation = [row for row in events if row['kind'] == 'CONTINUATION_HOLD_CHECK']
        cases[case] = {
            'trial_id': trial,
            'main_rgb_reports': len(reports),
            'main_report_status_counts': dict(Counter(row['report']['status'] for row in reports)),
            'recovery_requests': len(requests), 'preflight_refresh_calls': len(refreshed),
            'refresh_log_copies_not_extra_calls': len(repeated_refresh),
            'accepted_macro_attempts': len(accepted),
            'accepted_event_counter_snapshots': [row['attempts'] for row in accepted],
            'allocated_attempt_numbers': [row['accepted_attempt_no'] for row in accepted],
            'macro_operations': len(operations), 'macro_sdk_dispatches': len(commands),
            'all_sdk_dispatches': len(trace['actions']),
            'post_macro_reports': len(checks),
            'post_macro_status_counts': dict(Counter(row['report']['status'] for row in checks)),
            'new_generation_baseline_reports': len(baseline),
            'baseline_status_counts': dict(Counter(row['report']['status'] for row in baseline)),
            'continuation_hold_reports': len(continuation),
            'continuation_status_counts': dict(Counter(row['report']['status'] for row in continuation)),
            'help_records_in_main_stream': sum(row['kind'] == 'HELP_REQUESTED' for row in events),
        }
    return {'schema': 'pre-event-layer-summary/1', 'cases': cases, 'source_sha256': sources,
            'scope': 'frozen diagnostic object and event mapping; no product or human acceptance',
            'independence_claim': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = summarize(args.root)
    with args.output.open('x', encoding='utf8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False, indent=2))
