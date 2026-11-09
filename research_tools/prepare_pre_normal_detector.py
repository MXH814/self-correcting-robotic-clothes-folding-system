"""Small, source-bound normal trial intake and formal RND development package.

Controller intent is reconstructed from past command events at image render
time, never from injection phase or future outcome. Technical agent review is
explicitly distinct from Hu's/human independent experiment acceptance.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import time

import numpy as np

from .diagnostics import require
from .detection_encoder import ENCODER_VERSION, file_hash
from .shared_context import content_hash

PHASE_MAPPING_VERSION = 'fold-tops-command-intent-render-time/1'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def controller_phase_at(events, rendering_time_s, *, separate_sleeves=False):
    """Return intent for a rendered image; same-time events remain ambiguous.

    End events preserve the intent until the next BEGIN/hand command. Lift and
    transfer of either sleeve share HOLD. Closing alone and uninstrumented
    bimanual bottom folding remain OTHER. Planned opens are RELEASE.
    """
    phase, source = 'OTHER', None
    for event in events:
        if event['clock']['sim_time_s'] >= rendering_time_s:
            continue
        if event['kind'] == 'NORMAL_ACTION_BEGIN':
            phase = 'HOLD' if (event.get('arm') in ('left', 'right')
                and event.get('operation') in ('lift', 'transfer')
                and event.get('expected_hold') is True) else 'OTHER'
            source = event
        elif event['kind'] == 'NORMAL_HAND_COMMAND':
            if event.get('planned_release') is True and 'open' in (event.get('left'), event.get('right')):
                phase = 'RELEASE'
                source = event
            elif 'close' in (event.get('left'), event.get('right')):
                phase, source = 'OTHER', event
    if separate_sleeves and phase == 'HOLD':
        phase = source['arm'].upper() + '_SLEEVE_HOLD'
    return phase, source


def shared_detector_context(context, garment_id='TCLC_018', *, separate_sleeves=False):
    """Sensor/control identity excludes per-trial geometry and entry wrappers.

    Exact camera config, actual controller sources, trace/camera-chain source
    fingerprints, physics/sample profile and preprocessing remain bound.
    Entry scripts may change to call detection without changing these fields.
    """
    require(context.get('schema') == 'full-fold-continuation-context/1', 'invalid context')
    controller = context['controller']
    capture = {k: controller['wrapper_sha256'][k] for k in
               ('fold_recovery_chain.py', 'garment_observation_trace.py')}
    return {'schema': 'pre-observation-context/1', 'garment_id': garment_id,
        'camera': context['camera'], 'controller_upstream_sha256': controller['upstream_sha256'],
        'capture_sources_sha256': capture,
        'physics_dt_s': context['execution_profile']['physics_dt_s'],
        'observation_interval_physics_steps': context['execution_profile']['observation_interval_physics_steps'],
        'phase_mapping': ('fold-tops-command-intent-render-time/sleeve-2' if separate_sleeves else PHASE_MAPPING_VERSION),
        'encoder_preprocessing': ENCODER_VERSION,
        'raw_rgb': 'uint8 RGB HWC 640x480; full image; unique rendering timestamps',
        'scope': 'small-development-only; not statistical guarantee or product authorization'}


def detector_context_reference(context, garment_id='TCLC_018', *, separate_sleeves=False):
    return 'pre-observation-context/1#sha256=' + content_hash(shared_detector_context(
        context, garment_id, separate_sleeves=separate_sleeves))


def prepare(source, output):
    from PIL import Image, ImageDraw, ImageFont
    from .garment_trace_intake import verify_files, validate_trace
    output.mkdir(parents=True, exist_ok=False)
    planned = dict(schema='pre-normal-partition-plan/1',
        frozen_before_scores=True, fit=['normal-01'], calibration=['normal-02'],
        heldout_development=['normal-03'], allowed_phases=['HOLD'],
        epochs=10, batch_size=64, learning_rate=1e-4, seed=17, window=5,
        max_gap_s=.25, quantile=.95, output_dim=128, threshold_tuning_on_heldout=False)
    write(output/'partition-plan.json', planned)
    summaries=[]
    contexts=[]
    for index,name in enumerate(('normal-01','normal-02','normal-03')):
        roots=list((source/name).glob('fold-recovery-*'))
        require(len(roots)==1,'expected one original trial')
        root=roots[0]
        manifest=verify_files(root)
        trace=read(root/'observation-trace.json')
        record=read(root/'full-fold-recovery.json')
        require(manifest['trial_id']==trace['trial_id']==record['trial_id'],'trial mismatch')
        require(record['injection'] is None and record['recovery_enabled'] is False
            and record['final_control_state']=='NORMAL_COLLECTION_COMPLETED','not a completed normal collection')
        events=[json.loads(x) for x in (root/'pre-demo-events.jsonl').read_text(encoding='utf-8').splitlines()]
        require(all(e['trial_id']==trace['trial_id'] for e in events),'cross-trial events')
        require(all(a['clock']['sim_time_s']<=b['clock']['sim_time_s'] for a,b in zip(events,events[1:])), 'event ordering')
        context=shared_detector_context(read(root/'continuation-context.json'),record['garment'])
        contexts.append(context)
        with np.load(root/'rgb-frames.npz',allow_pickle=False) as a: frames=a['rgb']
        validate_trace(trace,frames)
        byframe={}
        for obs in trace['observations']: byframe.setdefault(obs['frame_index'],obs)
        phases=[]
        mappings=[]
        for i in range(len(frames)):
            obs=byframe[i]
            phase,event=controller_phase_at(events,obs['rendering_time_s'])
            phases.append(phase)
            mappings.append({'frame_index':i,'observation_id':obs['observation_id'],
                'rendering_time_s':obs['rendering_time_s'],'phase':phase,
                'source_command_sequence': event['sequence'] if event else None,
                'source_command_sim_s':event['clock']['sim_time_s'] if event else None})
        # Review first/middle/last samples of each hold episode and planned release.
        held=[i for i,p in enumerate(phases) if p=='HOLD']
        episodes=[]
        for i in held:
            if not episodes or i>episodes[-1][-1]+1: episodes.append([])
            episodes[-1].append(i)
        selected=[]
        for episode in episodes:
            selected += [episode[0],episode[len(episode)//2],episode[-1],min(len(frames)-1,episode[-1]+6)]
        selected += [0,len(frames)-1]
        sheet=Image.new('RGB',(1280,((len(selected)+3)//4)*270),'#16212a')
        draw=ImageDraw.Draw(sheet)
        font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',17)
        for j,i in enumerate(selected):
            x,y=(j%4)*320,(j//4)*270
            sheet.paste(Image.fromarray(frames[i]).resize((320,240)),(x,y+30))
            draw.text((x+5,y+4),f"{name} f{i} {byframe[i]['rendering_time_s']:.3f}s {phases[i]}",font=font,fill='white')
        sheet.save(output/(name+'-review.jpg'),quality=95)
        write(output/(name+'-phase-map.json'),mappings)
        summaries.append({'name':name,'source':str(root.resolve()),'trial_id':trace['trial_id'],
            'manifest_sha256':file_hash(root/'manifest.json'),'trace_sha256':file_hash(root/'observation-trace.json'),
            'rgb_sha256':file_hash(root/'rgb-frames.npz'),'events_sha256':file_hash(root/'pre-demo-events.jsonl'),
            'frames':len(frames),'phase_counts':dict(Counter(phases)),
            'hold_episodes':[[byframe[e[0]]['rendering_time_s'],byframe[e[-1]]['rendering_time_s']] for e in episodes],
            'review_frames':selected,'review_sheet':name+'-review.jpg','normal_review':None})
        print('Verified original trial',name,'frames',len(frames),'phases',Counter(phases),flush=True)
    require(all(c==contexts[0] for c in contexts),'mixed actual sensor/controller contexts')
    write(output/'shared-context.json',contexts[0])
    write(output/'intake.json',{'schema':'pre-normal-intake/1','trials':summaries,
        'context_reference':'pre-observation-context/1#sha256='+content_hash(contexts[0]),
        'independent_human_review':'pending','fit_started':False})


def train(output,weights):
    import torch
    from .detection_encoder import FrozenRGBEncoder
    from .observation_detector import fit, load_package, OnlineObservationDetector
    torch.set_num_threads(4)
    intake=read(output/'intake.json')
    review=read(output/'technical-review.json')
    plan=read(output/'partition-plan.json')
    require(review['reviewer_kind']=='agent-technical-review' and review['independent_human_review']=='pending','review identity must be explicit')
    require(review['scope']=='small-development-fit-only','review scope')
    require(set(review['accepted_trial_ids'])=={t['trial_id'] for t in intake['trials']},'normal declarations required')
    require(review['intake_sha256']==file_hash(output/'intake.json'),'review not bound to intake')
    encoder=FrozenRGBEncoder(weights,device='cpu')
    parts={'fit':[],'calibration':[]}
    allrows={}
    for trial in intake['trials']:
        root=Path(trial['source'])
        require(file_hash(root/'rgb-frames.npz')==trial['rgb_sha256'],'RGB changed after review')
        require(file_hash(root/'observation-trace.json')==trial['trace_sha256'],'trace changed after review')
        require(file_hash(root/'pre-demo-events.jsonl')==trial['events_sha256'],'events changed after review')
        trace=read(root/'observation-trace.json')
        events=[json.loads(x) for x in (root/'pre-demo-events.jsonl').read_text(encoding='utf-8').splitlines()]
        with np.load(root/'rgb-frames.npz',allow_pickle=False) as a: rgb=a['rgb']
        vectors=[]
        start=time.monotonic()
        for i in range(0,len(rgb),8):
            vectors.extend(encoder.encode(rgb[i:i+8]).tolist())
            if i%80==0: print('Encoding',trial['name'],i,'/',len(rgb),flush=True)
        rows=[]
        seen=set()
        for obs in trace['observations']:
            if obs['frame_index'] in seen: continue
            seen.add(obs['frame_index'])
            rows.append({'trial_id':trace['trial_id'],'lineage_group':trace['trial_id'],
                'observation_id':obs['observation_id'],'frame_id':str(obs['rendering_frame']),
                'sim_time_s':obs['rendering_time_s'],'read_sim_time_s':obs['camera_read_end']['sim_time_s'],
                'phase':controller_phase_at(events,obs['rendering_time_s'])[0],
                'context_reference':intake['context_reference'],'encoder_reference':encoder.reference,
                'embedding':vectors[obs['frame_index']]})
        fp=output/(trial['name']+'-features.jsonl')
        with fp.open('x',encoding='utf-8') as f:
            for row in rows: f.write(json.dumps(row,allow_nan=False)+'\n')
        allrows[trial['name']]=rows
        entry={'features':str(fp.resolve()),'feature_sha256':file_hash(fp),
               'source_reference':'manifest.json#sha256='+trial['manifest_sha256'],
               'normal_review':True,'review_reference':str((output/'technical-review.json').resolve())+'#sha256='+file_hash(output/'technical-review.json')}
        for role in parts:
            if trial['name'] in plan[role]: parts[role].append(entry)
        print('Encoded',trial['name'],len(rows),'frames in',time.monotonic()-start,'s',flush=True)
        del rgb,vectors
    write(output/'partitions.json',parts)
    meta=fit(parts,output/'package',phases=plan['allowed_phases'],epochs=plan['epochs'],
        batch_size=plan['batch_size'],learning_rate=plan['learning_rate'],seed=plan['seed'],
        window=plan['window'],max_gap_s=plan['max_gap_s'],quantile=plan['quantile'],output_dim=plan['output_dim'])
    print('FIT_COMPLETE',json.dumps(meta['training']), 'threshold',meta['threshold'],flush=True)
    model,loaded=load_package(output/'package',encoder_reference=encoder.reference,context_reference=intake['context_reference'])
    summaries=[]
    for name,rows in allrows.items():
        detector=OnlineObservationDetector(model,loaded)
        reports=[]
        for row in rows:
            report=detector.detect(row,generation=0,captured_wall_s=row['sim_time_s'],now_wall_s=row['sim_time_s'])
            report.update(replay=True,wall_latency_measured=False,controller_phase=row['phase'])
            reports.append(report)
        with (output/(name+'-scores.jsonl')).open('x',encoding='utf-8') as f:
            for report in reports: f.write(json.dumps(report,allow_nan=False)+'\n')
        summaries.append({'name':name,'trial_id':rows[0]['trial_id'],
            'role':next((k for k in ('fit','calibration','heldout_development') if name in plan[k])),
            'status_counts':dict(Counter(r['status'] for r in reports)),
            'reason_counts':dict(Counter(r['reason'] for r in reports)),
            'hold_max_score':max(r['score'] for r in reports if r['score'] is not None),
            'first_alarm':next((r['observed_sim_s'] for r in reports if r['status']=='ANOMALY'),None)})
    write(output/'result.json',{'schema':'pre-detector-development-result/1',
        'package_loaded':True,'package_id':meta['package_id'],'threshold':meta['threshold'],
        'context_reference':intake['context_reference'],'encoder_weights':str(weights.resolve()),
        'package_directory':str((output/'package').resolve()),'trials':summaries,
        'independent_human_review':'pending','statistical_guarantee':None,
        'small_development_package_only':True,'heldout_used_for_threshold':False})
    print('RESULT',json.dumps(summaries),flush=True)


def align_runtime_calibration(output):
    """Keep model/data/settings fixed; match calibration inference batch to online.

    Official fit calibrates with model_scores(batch_size=64), while the online
    detector uses batches of one. Floating point reduction order can otherwise
    trigger on its own maximum calibration window by approximately 1e-7. This
    only recomputes the normal-02 maximum using the online numerical path.
    The heldout-development trial never selects this threshold.
    """
    import torch
    from .observation_detector import load_package, read_features, model_scores, windowed, empirical_threshold, OnlineObservationDetector
    torch.set_num_threads(4)
    original=output/'package'
    destination=output/'package-runtime-parity'
    require(not destination.exists(),'parity package exists')
    manifest=read(original/'manifest.json')
    model,meta=load_package(original,encoder_reference=manifest['encoder_reference'],context_reference=manifest['context_reference'])
    parts=read(output/'partitions.json')
    maxima=[]
    for item in parts['calibration']:
        require(file_hash(item['features'])==item['feature_sha256'],'calibration file changed')
        rows=read_features(item['features'])
        scores=model_scores(model,rows,batch_size=1)
        values=windowed(rows,scores,meta['window'],meta['max_gap_s'],meta['allowed_phases'])
        maxima.append(max(x for x in values if x is not None))
    before=meta['threshold']
    parent=meta.pop('package_id')
    meta['threshold']=empirical_threshold(maxima,meta['quantile'])
    meta['calibration_trial_maxima']=maxima
    meta['calibration_inference_batch_size']=1
    meta['calibration_runtime_parity']={'parent_package_id':parent,
        'parent_threshold':before,'reason':'match batch=1 online numerical inference',
        'model_parameters_changed':False,'heldout_used':False}
    meta['package_id']=content_hash(meta)
    destination.mkdir()
    torch.save({'metadata':meta,'state_dict':model.state_dict()},destination/'detector.pt')
    write(destination/'manifest.json',dict(meta,checkpoint_sha256=file_hash(destination/'detector.pt')))
    loaded,verified=load_package(destination,encoder_reference=meta['encoder_reference'],context_reference=meta['context_reference'])
    # Ensure this correction cannot accidentally alter the learned parameters.
    require(all(torch.equal(a,b) for a,b in zip(model.state_dict().values(),loaded.state_dict().values())), 'model changed')
    results=[]
    for name in ('normal-01','normal-02','normal-03'):
        rows=read_features(output/(name+'-features.jsonl'))
        detector=OnlineObservationDetector(loaded,verified)
        reports=[]
        for row in rows:
            r=detector.detect(row,generation=0,captured_wall_s=row['sim_time_s'],now_wall_s=row['sim_time_s'])
            r.update(replay=True,wall_latency_measured=False,controller_phase=row['phase'])
            reports.append(r)
        with (output/(name+'-runtime-parity-scores.jsonl')).open('x',encoding='utf-8') as f:
            for r in reports:f.write(json.dumps(r,allow_nan=False)+'\n')
        results.append({'name':name,'trial_id':rows[0]['trial_id'],
            'role':{'normal-01':'fit','normal-02':'calibration','normal-03':'heldout_development'}[name],
            'status_counts':dict(Counter(r['status'] for r in reports)),
            'reason_counts':dict(Counter(r['reason'] for r in reports)),
            'max_score':max(r['score'] for r in reports if r['score'] is not None),
            'alarm_observations':[{'observation_id':r['observation_id'],'sim_time_s':r['observed_sim_s'],'score':r['score']} for r in reports if r['status']=='ANOMALY']})
    write(output/'runtime-parity-result.json',{'schema':'pre-runtime-parity-result/1',
        'package_id':meta['package_id'],'package_directory':str(destination.resolve()),
        'threshold':meta['threshold'],'old_threshold':before,'model_parameters_unchanged':True,
        'calibration_inference_batch_size':1,'heldout_used_for_threshold':False,
        'independent_human_review':'pending','small_development_package_only':True,'trials':results})
    print('RUNTIME_PARITY_RESULT',json.dumps(results),'threshold',meta['threshold'],flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    prep=sub.add_parser('prepare'); prep.add_argument('--source',type=Path,required=True);prep.add_argument('--output',type=Path,required=True)
    tr=sub.add_parser('train');tr.add_argument('--output',type=Path,required=True);tr.add_argument('--weights',type=Path,required=True)
    parity=sub.add_parser('align-runtime-calibration');parity.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.command=='prepare': prepare(a.source,a.output)
    elif a.command=='train': train(a.output,a.weights)
    else: align_runtime_calibration(a.output)


if __name__=='__main__': main()
