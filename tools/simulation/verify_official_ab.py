"""Audit recorded A/B executions without assigning independent acceptance."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

import numpy as np

import pre_detection_bridge  # Establish the repository import path for Isaac launchers.
from research_tools.detection_recovery import GeometryHoldMonitor
from research_tools.garment_trace_intake import verify_files, validate_trace
from research_tools.observation_detector import FIELDS, METHOD


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def verify_geometry_report(actual, recorded):
    """Allow platform rounding only in derived geometry, preserving all decisions."""
    assert actual.keys()==recorded.keys()
    for key,value in actual.items():
        if key in ('distance_m','cloth_height_m'):
            assert math.isclose(value,recorded[key],rel_tol=0.,abs_tol=1e-12),key
        else:
            assert value==recorded[key],key


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
            metadata_package=config['detector_metadata']
            expected_threshold=metadata_package.get('phase_thresholds',{}).get(
                metadata['phase'],metadata_package['threshold'])
            assert report['threshold']==expected_threshold
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
        accepted=[e for e in journal if e.get('kind')=='MACRO_ACCEPTED']
        assert len(accepted)==1
        assert any(e.get('kind')=='REQUEST_RECOVERY_PREFLIGHT' for e in journal)
        gate,=[e for e in journal if e.get('schema')=='pre-external-preflight-evidence/1']
        assert gate['proposal_binding']['passed'] is True
        assert all(gate['permit'][name] is True for name in
            ('authority','measured_rest','queue_empty','macro_validated'))
        actions={a['command_id']:a for a in trace['actions']}
        for operation in macro:
            assert operation['command_ids']
            for command_id in operation['command_ids']:
                assert actions[command_id]['issue']['wall_monotonic_ns']/1e9 >= gate['permit']['now_wall_s']
                feedback=actions[command_id]['feedback_observation_id']
                assert feedback is None or feedback in observations
    checks=[e for e in events if e['kind']=='RECOVERY_CHECK']
    passed_checks=[e for e in checks if e['request']['kind']=='REQUEST_FIXED_CONTINUATION']
    for event in passed_checks:
        assert event['report']['status']=='HELD'
        assert event['report']['window_start_sim_s']>macro[-1]['end']['sim_time_s']
        assert event['report']['provenance']=='privileged_sim_material_patch'
    continuation_checks=[e for e in events if e['kind']=='CONTINUATION_HOLD_CHECK']
    continuation_baseline=[e for e in events if e['kind']=='CONTINUATION_BASELINE']
    continuation_ood=0
    if continuation_checks:
        assert config['verified_continuation_policy']=='continuous-simulation-hold-with-rgb-ood-journal/1'
        assert passed_checks and len(macro)==5 and record['pre_scenario']=='fault-b'
        measurements=[json.loads(line) for line in (root/'execution-measurements.jsonl').read_text(encoding='utf-8').splitlines()]
        material={m['sample']['observation_id']:m for m in measurements if m['kind']=='material_patch'}
        profile={k:v for k,v in record['geometry_profile'].items() if k!='scope'}
        monitor=GeometryHoldMonitor(**profile)
        previous_time=macro[-1]['end']['sim_time_s']
        enabled,=[e for e in events if e['kind']=='FIXED_CONTINUATION_ENABLED']
        planned_release=next(e for e in events if e['kind']=='NORMAL_HAND_COMMAND'
            and e['sequence']>enabled['sequence'] and e.get('left')=='open')
        for event in continuation_baseline+continuation_checks:
            report=event['report']
            measurement=material[report['observation_id']]
            sample=measurement['sample']
            assert measurement['patch_ids']==record['intended_patch_vertex_ids']
            assert sample['trial_id']==trace['trial_id'] and sample['generation']==enabled['generation']
            assert sample['sim_time_s']>previous_time
            previous_time=sample['sim_time_s']
            assert sample['observation_id'] in observations
            verify_geometry_report(monitor.update(**sample),report)
            if event['kind']=='CONTINUATION_HOLD_CHECK':
                assert enabled['sequence']<event['sequence']<planned_release['sequence']
                decision=event['request']
                assert decision['geometry_report']==report and decision['generation']==sample['generation']
                rgb_event=next(e for e in detections if e.get('request')==decision)
                assert rgb_event['observation']['phase'] in ('HOLD','LEFT_SLEEVE_HOLD')
                assert decision['raw_observation_status']==rgb_event['report']['status']
                rgb_ok=(rgb_event['report']['status'] in ('NORMAL','ANOMALY') or
                    (rgb_event['report']['status']=='UNKNOWN' and rgb_event['report']['reason']=='WINDOW_WARMUP'))
                assert (decision['kind']=='CONTINUE_VERIFIED_HOLD')==(report['status']=='HELD' and rgb_ok)
                continuation_ood+=rgb_event['report']['status']=='ANOMALY'
    status_counts=Counter(e['report']['status'] for e in detections)
    anomalies=[{'render_sim_s':e['observation']['sim_time_s'],
        'observation_id':e['observation']['observation_id'],'phase':e['observation']['phase'],
        'score':e['report']['score'],'threshold':e['report']['threshold']} for e in detections
        if e['report']['status']=='ANOMALY']
    injected=[e for e in events if e['kind']=='FAULT_INJECTION_BEGIN']
    completed=record['final_control_state']=='MONITORED_CONTROLLER_COMPLETED' and record.get('judgment') is not None
    judgment=record.get('judgment')
    if judgment is not None:
        with np.load(root/'final-point-cloud.npz',allow_pickle=False) as archive:
            points=archive['points']
        x0,x1,y0,y1=judgment['boundary_world_xy_m']
        inside=(points[:,0]>=x0)&(points[:,0]<=x1)&(points[:,1]>=y0)&(points[:,1]<=y1)
        assert int(inside.sum())==judgment['inside_count'] and len(points)==judgment['point_count']
    expected_case_pass=completed and not help_events and judgment.get('upstream_success') is True
    if record['pre_scenario']=='normal-a':
        expected_case_pass=expected_case_pass and not anomalies and record.get('recovery_attempts',0)==0
    else:
        expected_case_pass=expected_case_pass and bool(passed_checks) and len(macro)==5 and record.get('fixed_continuation_started') is True
    return dict(schema='official-ab-audit/1',trial_id=trace['trial_id'],scenario=record['pre_scenario'],
        source_hashes_verified=True,observations=len(observations),rgb_frames=len(rgb),dispatches=len(trace['actions']),
        continuous_unique_rgb_reports=len(detections),detection_status_counts=dict(status_counts),
        detection_phase_counts=dict(Counter(e['observation']['phase'] for e in detections)),
        anomaly_reports=anomalies,first_injection_sim_s=injected[0]['clock']['sim_time_s'] if injected else None,
        dispatches_after_help=after_help,recovery_attempts=record.get('recovery_attempts',0),
        macro_operations=[m['operation'] for m in macro],
        macro_dispatches=sum(len(m['command_ids']) for m in macro),
        continuous_geometry_checks=len(checks),hold_check_passed=bool(passed_checks),
        hold_check_method='privileged_sim_material_patch' if checks else None,
        hold_check_report=passed_checks[-1]['report'] if passed_checks else None,
        continuation_geometry_checks=len(continuation_checks),
        continuation_geometry_recomputed=bool(continuation_checks),
        continuation_raw_ood_reports=continuation_ood,
        continuation_policy=config.get('verified_continuation_policy'),
        fixed_continuation_started=record.get('fixed_continuation_started',False),
        final_state=record['final_control_state'],help_reason=record.get('help_reason'),
        complete_fold_recorded=completed,expected_case_automatic_checks_passed=bool(expected_case_pass),
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
