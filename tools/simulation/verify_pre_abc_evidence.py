"""Verify complete video decoding, past-only alignment and original screenshot pixels."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            digest.update(chunk)
    return digest.hexdigest()


def verify(root,ffmpeg):
    manifest=read(root/'manifest.json')
    video=root/manifest['video']['file']
    assert sha(video)==manifest['video']['sha256']
    decoded=subprocess.run([str(ffmpeg),'-v','error','-i',str(video),'-progress','pipe:1',
        '-nostats','-f','null','-'],capture_output=True)
    assert decoded.returncode==0 and not decoded.stderr,decoded.stderr
    frame_counts=[int(n) for n in re.findall(rb'frame=(\d+)',decoded.stdout)]
    assert frame_counts[-1]==manifest['video']['frames']
    mapping=list(csv.DictReader((root/'video-frame-map.csv').open(encoding='utf-8-sig')))
    assert len(mapping)==manifest['video']['frames']
    sources={}
    replay={entry['trial_id']:entry['events'] for entry in read(root/'replay-events.json')}
    for clip in manifest['clips']:
        source=Path(clip['source_directory'])
        assert source.is_absolute()
        for name,info in clip['source_files'].items():
            assert sha(source/name)==info['sha256']
        trace=read(source/'observation-trace.json')
        obs={o['observation_id']:o for o in trace['observations']}
        sources[clip['trial_id']]=(source,obs)
    for number,row in enumerate(mapping):
        assert int(row['video_frame'])==number
        assert abs(float(row['video_time_s'])-number/manifest['video']['fps'])<1e-8
        source,observations=sources[row['trial_id']]
        obs=observations[row['observation_id']]
        target=float(row['target_sim_s'])
        assert obs['frame_index']==int(row['source_frame_index'])
        assert obs['rendering_time_s']==float(row['rendering_time_s'])<=target+1e-9
        reports=[e for e in replay[row['trial_id']] if e['kind'] in
            ('OFFICIAL_DETECTION','PREFLIGHT_REDETECTION') and e['clock']['sim_time_s']<=target+1e-9]
        if reports:
            assert row['detection_observation_id']==reports[-1]['report']['observation_id']
            assert float(row['detection_log_sim_s'])==reports[-1]['clock']['sim_time_s']
        else:
            assert row['detection_observation_id']==row['detection_log_sim_s']==''
    shots=read(root/'截图索引.json')
    assert len(shots)==8
    for shot in shots:
        assert sha(root/shot['file'])==shot['annotated_sha256']
        assert sha(root/shot['raw_file'])==shot['raw_sha256']
        source,observations=sources[shot['trial_id']]
        obs=observations[shot['observation_id']]
        assert obs['frame_index']==shot['source_frame_index']
        assert obs['rendering_time_s']==shot['rendering_time_s']<=shot['replay_log_sim_s']+1e-9
        with np.load(source/'rgb-frames.npz',allow_pickle=False) as archive:
            assert np.array_equal(np.asarray(Image.open(root/shot['raw_file'])),archive['rgb'][shot['source_frame_index']])
        if shot['file'].startswith('关键截图/06_'):
            macro=read(source/'full-fold-recovery.json')['macro_execution']
            assert obs['rendering_time_s']>macro[-1]['end']['sim_time_s']
    chosen=[]
    for clip in manifest['clips']:
        first,last=clip['first_video_frame'],clip['end_video_frame_exclusive']-1
        chosen.extend([(first+last)//2,last])
    qa=root/'画面核验'
    qa.mkdir(exist_ok=True)
    expression='+'.join(f'eq(n\\,{n})' for n in chosen)
    result=subprocess.run([str(ffmpeg),'-v','error','-i',str(video),'-vf',f'select={expression}',
        '-fps_mode','vfr','-y',str(qa/'decoded-%02d.png')],capture_output=True)
    assert result.returncode==0,result.stderr
    sheet=Image.new('RGB',(1600,1440),'#101923')
    draw=ImageDraw.Draw(sheet)
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',22)
    for index,number in enumerate(chosen):
        x,y=(index%2)*800,(index//2)*480
        picture=Image.open(qa/f'decoded-{index+1:02d}.png')
        assert picture.size==(1600,900)
        sheet.paste(picture.resize((800,450)),(x,y+30))
        draw.text((x+12,y+1),f"视频 {number/manifest['video']['fps']:.2f}s / {mapping[number]['segment']}",font=font,fill='white')
    sheet.save(root/'视频画面核验.jpg',quality=94)
    result=dict(schema='z3-abc-render-qa/1',full_decode_passed=True,decoded_frames=frame_counts[-1],
        duration_s=manifest['video']['duration_s'],video_sha256=sha(video),
        frame_mapping_verified=len(mapping),past_only_detection_alignment_verified=True,
        raw_screenshots_pixel_identical_to_sources=len(shots),strict_post_macro_frame_verified=True,
        agent_visual_review='pending',browser_player_tested=False,
        experimental_independent_review='pending')
    (root/'visual-qa.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path)
    parser.add_argument('--ffmpeg',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(verify(args.root.resolve(),args.ffmpeg),ensure_ascii=False,indent=2))
