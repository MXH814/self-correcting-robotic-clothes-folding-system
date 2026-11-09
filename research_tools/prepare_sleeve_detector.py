"""Prepare sleeve-conditioned calibration with complete-trial provenance."""
import argparse
from collections import Counter
import json
from pathlib import Path

import numpy as np

from .detection_encoder import FrozenRGBEncoder, file_hash
from .diagnostics import require
from .garment_trace_intake import verify_files, validate_trace
from .observation_detector import fit, load_package, OnlineObservationDetector
from .prepare_pre_normal_detector import (controller_phase_at, detector_context_reference,
                                         read, shared_detector_context, write)
from .shared_context import content_hash


def prepare(baseline, additional, output):
    from PIL import Image, ImageDraw, ImageFont
    output.mkdir(parents=True, exist_ok=False)
    # Revision 1's development trial is now calibration data. New A/B runs
    # remain separate from these reviewed normal records.
    plan = dict(schema='sleeve-calibration-plan/1', seed=17, epochs=10,
                batch_size=64, learning_rate=.0001, window=5, max_gap_s=.25,
                quantile=.95, calibration_inference_batch_size=1,
                phases=['LEFT_SLEEVE_HOLD', 'RIGHT_SLEEVE_HOLD'],
                fit=['original-normal-01'],
                calibration=['original-normal-02', 'original-normal-03', 'additional-01', 'additional-02'],
                prior_development_records=['original-normal-03', 'official-A-04', 'official-B-01'],
                new_acceptance='New A/B trials after package frozen', normal_review='agent technical review')
    write(output/'plan.json', plan)
    intake = read(baseline/'intake.json')
    sources = [(f'original-{trial["name"]}', Path(trial['source']), baseline/(trial['name']+'-features.jsonl'))
               for trial in intake['trials']]
    for number in (1, 2):
        paths = list((additional/f'normal-{number:02}').glob('fold-recovery-*'))
        require(len(paths)==1, 'One completed additional trial is required')
        sources.append((f'additional-{number:02}', paths[0], None))
    entries, shared = [], []
    for name, source, prior_features in sources:
        manifest = verify_files(source)
        record = read(source/'full-fold-recovery.json')
        require(record.get('injection') is None and record.get('recovery_enabled') is False
                and record.get('final_control_state')=='NORMAL_COLLECTION_COMPLETED', 'Complete normal trial required')
        context = read(source/'continuation-context.json')
        shared.append(shared_detector_context(context, separate_sleeves=True))
        events = [json.loads(line) for line in (source/'pre-demo-events.jsonl').read_text(encoding='utf-8').splitlines()]
        trace = read(source/'observation-trace.json')
        with np.load(source/'rgb-frames.npz', allow_pickle=False) as archive:
            rgb = archive['rgb']
        validate_trace(trace, rgb)
        by_frame = {}
        for obs in trace['observations']:
            by_frame.setdefault(obs['frame_index'], obs)
        phases = [controller_phase_at(events, by_frame[i]['rendering_time_s'], separate_sleeves=True)[0]
                  for i in range(len(rgb))]
        selected = [0, len(rgb)-1]
        for phase in plan['phases']:
            frames = [i for i, value in enumerate(phases) if value==phase]
            require(bool(frames), 'Missing expected sleeve phase')
            selected.extend([frames[0], frames[len(frames)//2], frames[-1], min(frames[-1]+6, len(rgb)-1)])
        sheet = Image.new('RGB', (1280, 810), '#15212d')
        draw = ImageDraw.Draw(sheet)
        face = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 15)
        for i, frame in enumerate(selected):
            x, y = i%4*320, i//4*270
            sheet.paste(Image.fromarray(rgb[frame]).resize((320, 240)), (x, y+30))
            draw.text((x+3, y+5), f"f{frame} {by_frame[frame]['rendering_time_s']:.3f}s {phases[frame]}",font=face,fill='white')
        sheet.save(output/(name+'-review.jpg'), quality=95)
        entries.append(dict(name=name, source=str(source.resolve()), prior_features=str(prior_features.resolve()) if prior_features else None,
            trial_id=trace['trial_id'], manifest_sha256=file_hash(source/'manifest.json'),
            rgb_sha256=file_hash(source/'rgb-frames.npz'), events_sha256=file_hash(source/'pre-demo-events.jsonl'),
            trace_sha256=file_hash(source/'observation-trace.json'),
            prior_features_sha256=file_hash(prior_features) if prior_features else None,
            phase_counts=dict(Counter(phases)), review_image=name+'-review.jpg'))
    require(all(context==shared[0] for context in shared), 'Sensor/controller configurations differ')
    write(output/'intake.json',dict(trials=entries,context_reference=detector_context_reference(context, separate_sleeves=True),
                                  shared_context=shared[0], independent_human_review='pending'))
    print('INTAKE_READY', output, flush=True)


def train(output, weights):
    import torch
    torch.set_num_threads(4)
    plan, intake, review = (read(output/name) for name in ('plan.json','intake.json','technical-review.json'))
    require(review['intake_sha256']==file_hash(output/'intake.json')
            and review['reviewer_kind']=='agent-technical-review', 'Bound technical review required')
    require(set(review['accepted_trial_ids'])=={trial['trial_id'] for trial in intake['trials']}, 'Review all trials')
    encoder = FrozenRGBEncoder(weights, 'cpu')
    partitions = {'fit': [], 'calibration': []}
    for trial in intake['trials']:
        source = Path(trial['source'])
        for filename, key in [('rgb-frames.npz','rgb_sha256'), ('observation-trace.json','trace_sha256'),
                              ('pre-demo-events.jsonl','events_sha256')]:
            require(file_hash(source/filename)==trial[key], 'Source changed after review')
        trace = read(source/'observation-trace.json')
        events = [json.loads(line) for line in (source/'pre-demo-events.jsonl').read_text(encoding='utf-8').splitlines()]
        prior = trial['prior_features']
        if prior:
            require(file_hash(prior)==trial['prior_features_sha256'], 'Prior feature archive changed')
            rows = [json.loads(line) for line in Path(prior).read_text(encoding='utf-8').splitlines()]
        else:
            with np.load(source/'rgb-frames.npz',allow_pickle=False) as archive:
                rgb = archive['rgb']
            vectors = []
            for start in range(0, len(rgb), 8):
                vectors.extend(encoder.encode(rgb[start:start+8]).tolist())
            seen, rows = set(), []
            for obs in trace['observations']:
                if obs['frame_index'] in seen:
                    continue
                seen.add(obs['frame_index'])
                rows.append(dict(trial_id=trace['trial_id'], lineage_group=trace['trial_id'],
                    observation_id=obs['observation_id'], frame_id=str(obs['rendering_frame']),
                    sim_time_s=obs['rendering_time_s'],read_sim_time_s=obs['camera_read_end']['sim_time_s'],
                    encoder_reference=encoder.reference,embedding=vectors[obs['frame_index']]))
        for row in rows:
            row['phase'] = controller_phase_at(events,row['sim_time_s'],separate_sleeves=True)[0]
            row['context_reference'] = intake['context_reference']
        path = output/(trial['name']+'-features.jsonl')
        with path.open('x',encoding='utf-8') as stream:
            for row in rows:
                stream.write(json.dumps(row,allow_nan=False)+'\n')
        role = 'fit' if trial['name'] in plan['fit'] else 'calibration'
        partitions[role].append(dict(features=str(path.resolve()),feature_sha256=file_hash(path),
            source_reference='manifest.json#sha256='+trial['manifest_sha256'],normal_review=True,
            review_reference=str(output/'technical-review.json')+'#sha256='+file_hash(output/'technical-review.json')))
        print('FEATURES_READY',trial['name'],len(rows),flush=True)
    write(output/'partitions.json',partitions)
    metadata = fit(partitions,output/'package',phases=plan['phases'],epochs=plan['epochs'],
        batch_size=plan['batch_size'],learning_rate=plan['learning_rate'],seed=plan['seed'],
        window=plan['window'],max_gap_s=plan['max_gap_s'],quantile=plan['quantile'],
        calibrate_by_phase=True,calibration_batch_size=1)
    model, meta = load_package(output/'package',encoder_reference=encoder.reference,
                               context_reference=intake['context_reference'])
    write(output/'result.json',dict(package_id=meta['package_id'],phase_thresholds=meta['phase_thresholds'],
        calibration_phase_trial_maxima=meta['calibration_phase_trial_maxima'],
        context_reference=meta['context_reference'],independent_human_review='pending'))
    print('PACKAGE_READY',json.dumps(meta['phase_thresholds']),flush=True)


def preserve_normal_floor(output, baseline_package):
    """Keep the previous pooled normal calibration envelope when splitting phases."""
    import torch
    manifest=read(output/'package/manifest.json')
    model,meta=load_package(output/'package',encoder_reference=manifest['encoder_reference'],
                            context_reference=manifest['context_reference'])
    baseline_manifest=read(baseline_package/'manifest.json')
    baseline,baseline_meta=load_package(baseline_package,encoder_reference=manifest['encoder_reference'],
                                       context_reference=baseline_manifest['context_reference'])
    require(all(torch.equal(value,baseline.state_dict()[key]) for key,value in model.state_dict().items()),
            'A calibration floor requires the same learned score model')
    floor=baseline_meta['threshold']
    parent=meta.pop('package_id')
    meta['phase_thresholds']={phase:max(value,floor) for phase,value in meta['phase_thresholds'].items()}
    meta['phase_threshold_floor_reference']=dict(parent_package_id=parent,
        baseline_package_id=baseline_meta['package_id'],baseline_manifest_sha256=file_hash(baseline_package/'manifest.json'),
        threshold=floor,source='previous independent normal calibration',model_parameters_unchanged=True)
    meta['threshold_method']='empirical-phase-trial-maxima-with-pooled-normal-calibration-floor/1'
    meta['package_id']=content_hash(meta)
    destination=output/'package-preserved-floor'
    destination.mkdir(exist_ok=False)
    torch.save(dict(metadata=meta,state_dict=model.state_dict()),destination/'detector.pt')
    write(destination/'manifest.json',dict(meta,checkpoint_sha256=file_hash(destination/'detector.pt')))
    load_package(destination,encoder_reference=meta['encoder_reference'],context_reference=meta['context_reference'])
    write(output/'normal-floor-result.json',dict(package_directory=str(destination.resolve()),
        package_id=meta['package_id'],phase_thresholds=meta['phase_thresholds'],
        floor_reference=meta['phase_threshold_floor_reference']))
    print('NORMAL_FLOOR_PACKAGE_READY',json.dumps(meta['phase_thresholds']),flush=True)


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('prepare','train','preserve-normal-floor'))
    parser.add_argument('--baseline',type=Path)
    parser.add_argument('--additional',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--weights',type=Path)
    parser.add_argument('--baseline-package',type=Path)
    args = parser.parse_args()
    if args.command=='prepare':
        prepare(args.baseline,args.additional,args.output)
    elif args.command=='train':
        train(args.output,args.weights)
    else:
        preserve_normal_floor(args.output,args.baseline_package)
