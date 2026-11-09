"""Audit recorded A/B executions without assigning independent acceptance."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np

import pre_detection_bridge  # Establish the repository import path for Isaac launchers.
from research_tools.garment_trace_intake import verify_files, validate_trace
from research_tools.observation_detector import FIELDS, METHOD


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def audit(root):
    verify_files(root)
    trace=read(root/'observation-trace.json')
    record=read(root/'full-fold-recovery.json')
    config=read(root/'official-ab-config.json')
    assert trace['trial_id']==record['trial_id']==config['trial_id']
    with np.load(root/'rgb-frames.npz',allow_pickle=False) as archive:
        rgb=archive['rgb']
    validate_trace(trace,rgb)
    for name,digest in config['producer_sha256'].items():
        assert hashlib.sha256((root/'source-snapshot'/name).read_bytes()).hexdigest()==digest
    events=[json.loads(line) for line in (root/'pre-demo-events.jsonl').read_text(encoding='utf-8').splitlines()]
    journal=[json.loads(line) for line in (root/'official-workflow-events.jsonl').read_text(encoding='utf-8').splitlines()]
    observations={o['observation_id']:o for o in trace['observations']}
    detections=[e for e in events if e['kind']=='OFFICIAL_DETECTION']
    frames=[]
    for event in detections:
        metadata,report=event['observation'],event['report']
        assert set(metadata)==FIELDS-{'embedding'}
        assert report['method']==METHOD
        assert metadata['trial_id']==trace['trial_id']==report['trial_id']
        obs=observations[metadata['observation_id']]
        assert metadata['frame_id']==str(obs['rendering_frame'])
        assert metadata['sim_time_s']==obs['rendering_time_s']
        assert report['captured_wall_s']==obs['camera_read_begin']['wall_monotonic_ns']/1e9
        if report['status'] in ('NORMAL','ANOMALY'):
            assert report['package_id']==config['detector_metadata']['package_id']
            assert report['context_reference']==config['context_reference']
            assert (report['score']>report['threshold'])==(report['status']=='ANOMALY')
        frames.append(metadata['frame_id'])
    assert len(frames)==len(set(frames))
    help_events=[e for e in events if e['kind']=='HELP_REQUESTED']
    after_help=None
    if help_events:
        assert len(help_events)==1
        after_help=sum(a['issue']['wall_monotonic_ns']>help_events[0]['clock']['wall_monotonic_ns'] for a in trace['actions'])
        assert after_help==0
        assert record['dispatch_count_at_help']==record['dispatch_count_at_exit']==len(trace['actions'])
    macro=record.get('macro_execution',[])
    if macro:
        expected=['release','retreat','regrasp','close','lift']
        assert [m['operation'] for m in macro]==expected[:len(macro)]
        accepted=[e for e in journal if e['kind']=='MACRO_ACCEPTED']
        assert len(accepted)==1
        assert any(e['kind']=='REQUEST_RECOVERY_PREFLIGHT' for e in journal)
        actions={a['command_id']:a for a in trace['actions']}
        for operation in macro:
            assert operation['command_ids']
            for command_id in operation['command_ids']:
                feedback=actions[command_id]['feedback_observation_id']
                assert feedback is None or feedback in observations
    status_counts=Counter(e['report']['status'] for e in detections)
    anomalies=[{'render_sim_s':e['observation']['sim_time_s'],
        'observation_id':e['observation']['observation_id'],'phase':e['observation']['phase'],
        'score':e['report']['score'],'threshold':e['report']['threshold']} for e in detections
        if e['report']['status']=='ANOMALY']
    injected=[e for e in events if e['kind']=='FAULT_INJECTION_BEGIN']
    return dict(schema='official-ab-audit/1',trial_id=trace['trial_id'],scenario=record['pre_scenario'],
        source_hashes_verified=True,observations=len(observations),rgb_frames=len(rgb),dispatches=len(trace['actions']),
        continuous_unique_rgb_reports=len(detections),detection_status_counts=dict(status_counts),
        detection_phase_counts=dict(Counter(e['observation']['phase'] for e in detections)),
        anomaly_reports=anomalies,first_injection_sim_s=injected[0]['clock']['sim_time_s'] if injected else None,
        dispatches_after_help=after_help,recovery_attempts=record.get('recovery_attempts',0),
        macro_operations=[m['operation'] for m in macro],
        macro_dispatches=sum(len(m['command_ids']) for m in macro),
        fixed_continuation_started=record.get('fixed_continuation_started',False),
        final_state=record['final_control_state'],help_reason=record.get('help_reason'),
        upstream_region_proxy=record.get('judgment'),independent_human_review='pending',
        product_stop_acceptance=None)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=audit(args.root)
    with args.output.open('x',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2,ensure_ascii=False)
    print(json.dumps(result,ensure_ascii=False,indent=2))
