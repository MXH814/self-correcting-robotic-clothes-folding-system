"""Build an offline A/B/C replay with past-only score and event alignment."""
import argparse
import bisect
import csv
import html
import json
import math
from pathlib import Path
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

from build_pre_z3_evidence import FPS, SIZE, font, load_segment, read, sha, text, write

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from research_tools.garment_trace_intake import verify_files

TITLES = {'A': '正常运行联调', 'B': '观测告警触发恢复', 'C': '缺检测条件时求助'}
COLORS = {'A': '#72D8CD', 'B': '#F1BA69', 'C': '#B7A7F6'}
OPERATIONS = dict(release='释放', retreat='退让', regrasp='重抓', close='闭手', lift='抬升')
PHASES = dict(LEFT_SLEEVE_HOLD='左袖持有', RIGHT_SLEEVE_HOLD='右袖持有',
              HOLD='持有', LIFT='提起', RELEASE='计划释放', OTHER='其他阶段')


def load(root, key):
    root = root.resolve()
    verify_files(root)
    trace = read(root / 'observation-trace.json')
    segment = load_segment(dict(source_directory=str(root), trial_id=trace['trial_id'],
                               sim_start_s=trace['observations'][0]['rendering_time_s']), key)
    events = [json.loads(line) for line in (root / 'pre-demo-events.jsonl').read_text(encoding='utf-8').splitlines()]
    assert all(event['trial_id'] == trace['trial_id'] for event in events)
    segment.update(events=events, speed=2. if key == 'A' else 1., hold=3. if key == 'B' else 2.5,
                   intro=1., start=next(event['clock']['sim_time_s'] for event in events
                       if event['kind']=='FAULT_INJECTION_BEGIN') if key == 'B' else segment['times'][0],
                   end=events[-1]['clock']['sim_time_s'])
    return segment


def available(segment, target):
    return [event for event in segment['events'] if event['clock']['sim_time_s'] <= target + 1e-9]


def detection_events(events):
    return [event for event in events if event['kind'] in
            ('OFFICIAL_DETECTION', 'PREFLIGHT_REDETECTION')]


def current_state(segment, target, events):
    if any(event['kind'] == 'HELP_REQUESTED' for event in events):
        return '求助 / 自动派发关闭'
    if any(event['kind'] == 'FINAL_OUTCOME' for event in events):
        return '整次折叠完成'
    if segment['segment'] == 'B':
        for operation in segment['record'].get('macro_execution', []):
            if operation['begin']['sim_time_s'] <= target < operation['end']['sim_time_s']:
                return '恢复操作 · ' + OPERATIONS[operation['operation']]
        if any(event['kind'] == 'FIXED_CONTINUATION_ENABLED' for event in events):
            return '复检通过 / 固定流程接续'
        if any(event['kind'] == 'MACRO_RESULT' for event in events):
            return '恢复后连续持有检查'
        if any(event.get('request', {}).get('kind') == 'REQUEST_RECOVERY_PREFLIGHT'
               for event in detection_events(events) if event.get('request')):
            return '告警已确认 / 执行前检查'
    return '正常控制 / 观测检测'


def plot(draw, segment, events):
    x0, y0, width, height = 1032, 460, 514, 132
    draw.rectangle((x0, y0, x0 + width, y0 + height), fill='#172633', outline='#334B5D')
    reports = [event for event in detection_events(events) if event['report'].get('score') is not None
               and event['clock']['sim_time_s']>=segment['start']]
    if not reports:
        text(draw, (x0 + 18, y0 + 42), '当前没有可用窗口分数', 23, '#B8C7D5')
        return
    ymin, ymax = .5, 1.5
    def position(event, field='score'):
        t = event['clock']['sim_time_s']
        score = event['report'][field]
        return (x0 + (t - segment['start']) / (segment['end'] - segment['start']) * width,
                y0 + height - (score - ymin) / (ymax - ymin) * height)
    text(draw, (x0 + 5, y0 + height + 4), f"{segment['start']:.2f}s", 17, '#A9B9C8')
    text(draw, (x0 + width - 68, y0 + height + 4), f"{segment['end']:.2f}s", 17, '#A9B9C8')
    previous = None
    for event in reports:
        point = position(event)
        if previous and event['clock']['sim_time_s'] - previous[0] <= .26:
            draw.line((*previous[1], *point), fill=COLORS[segment['segment']], width=3)
            draw.line((*previous[2], *position(event, 'threshold')), fill='#CBA3F3', width=2)
        color = '#FF8F8F' if event['report']['status'] == 'ANOMALY' else COLORS[segment['segment']]
        draw.ellipse((point[0]-3, point[1]-3, point[0]+3, point[1]+3), fill=color)
        previous = event['clock']['sim_time_s'], point, position(event, 'threshold')


def render(segment, index, target, mode, caption=None):
    key = segment['segment']
    obs = segment['by_frame'][index]
    events = available(segment, target)
    detections = detection_events(events)
    latest = detections[-1] if detections else None
    im = Image.new('RGB', SIZE, '#101923')
    draw = ImageDraw.Draw(im)
    text(draw, (32, 19), '第三组 / FIPER RND-OE 观测分支适配', 23, '#A7B8C8')
    text(draw, (32, 54), key + '   ' + TITLES[key], 34, bold=True)
    text(draw, (1016, 24), '独立试次 / 离线回放', 26, COLORS[key])
    text(draw, (1016, 67), f'回放日志 {target:.3f} 仿真秒', 24)
    text(draw, (32, 103), f"全幅 RGB / 渲染 {obs['rendering_time_s']:.3f}s / 源帧 {index}", 18, '#B8C7D5')
    im.paste(Image.fromarray(segment['rgb'][index]).resize((960, 720), Image.Resampling.LANCZOS), (32, 128))
    label = {'intro': '片头静帧 1s', 'active': f"活动片段 {segment['speed']:g}× 仿真时间",
             'end': f"末帧停留 {segment['hold']:g}s / 最终日志", 'still': '静态备份 / 同试次记录'}[mode]
    text(draw, (1016, 131), label, 24, COLORS[key], bold=True)
    text(draw, (1016, 179), current_state(segment, target, events), 28, bold=True)
    if latest:
        report = latest['report']
        phase = latest.get('observation', {}).get('phase', 'HOLD')
        phase = PHASES.get(phase, phase)
        age = target-latest['clock']['sim_time_s']
        label = '历史检测  ' if age > .25 else '最近检测  '
        text(draw, (1016, 233), label + report['status'] + ' / ' + phase, 25, COLORS[key], bold=True)
        score = report.get('score')
        raw = report.get('raw_score')
        threshold = report.get('threshold')
        text(draw, (1016, 277), '窗口分数  ' + (f'{score:.6f}' if score is not None else '—'), 26)
        text(draw, (1016, 318), '原始分数  ' + (f'{raw:.6f}' if raw is not None else '—'), 24)
        text(draw, (1016, 358), '阈值  ' + (f'{threshold:.6f}' if threshold is not None else '—'), 24)
        text(draw, (1016, 404), f"检测日志 {latest['clock']['sim_time_s']:.3f}s / 距回放 {age:.3f}s", 19, '#A7B8C8')
    else:
        text(draw, (1016, 237), '等待首个检测报告', 25, '#B8C7D5')
    text(draw, (1032, 437), '五帧窗口分数 / 紫线为阈值', 16, '#A7B8C8')
    plot(draw, segment, events)
    if any(event['kind']=='FINAL_OUTCOME' for event in events):
        record=segment['record']
        judgment=record['judgment']
        if key=='A':
            note=f"完整折叠 / 恢复 {record['recovery_attempts']} 次\n非预期告警 {len(record.get('alerts', []))} 次"
        else:
            dispatches=sum(len(m['command_ids']) for m in record['macro_execution'])
            note=f"完整折叠 / 恢复 {record['recovery_attempts']} 次\n五操作 {dispatches} 条实际派发"
        note+=f"\n区域代理 {judgment['inside_count']}/{judgment['point_count']} / 独立审核待完成"
    elif current_state(segment, target, events).startswith('求助'):
        note=f"求助 / 恢复 {segment['record'].get('recovery_attempts', 0)} 次\n自动派发已关闭\n产品停车验收待完成"
    elif key == 'B':
        checks = [event for event in events if event['kind'] in ('RECOVERY_CHECK','CONTINUATION_HOLD_CHECK')]
        if checks:
            check = checks[-1]['report']
            label='历史几何' if target-checks[-1]['clock']['sim_time_s']>.25 else '新几何检查'
            note = f"{label} {check['status']} / {check.get('sample_count', 0)} 样本\n检查日志 {checks[-1]['clock']['sim_time_s']:.3f}s\n仿真内部材料片与指尖坐标"
        else:
            note = 'RGB 编码与五帧过去窗口\n执行前取得测量证据\n宏后采新观测检查持有'
    elif key == 'A':
        note = '无故障注入 / 持续检测\n计划释放保留阶段记录\n本轮为小规模开发验证'
    else:
        note = '检测包缺失时保留 UNKNOWN\n请求停止新增自动派发\n求助日志与最后 RGB 分别标时'
    text(draw, (1016, 640), note, 24, '#CFD9E2', width=548)
    if caption:
        text(draw, (1016, 783), caption, 20, '#FFFFFF', width=548)
    text(draw, (46, 857), f"试次 {segment['trial_id']} / 画面取自过去源帧 / 静帧停留单独标注", 20)
    return im, latest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('a', 'b', 'c', 'output', 'ffmpeg'):
        parser.add_argument('--' + key, type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    segments = [load(getattr(args, key.lower()), key) for key in 'ABC']
    video = out / 'Z3_ABC真实检测与恢复.mp4'
    if video.exists():
        raise FileExistsError('Preserve the previous video before generating a new version')
    command = [str(args.ffmpeg), '-hide_banner', '-loglevel', 'warning', '-n', '-f', 'rawvideo',
               '-pix_fmt', 'rgb24', '-s', '1600x900', '-r', str(FPS), '-i', '-', '-an',
               '-c:v', 'libx264', '-preset', 'fast', '-crf', '20', '-pix_fmt', 'yuv420p',
               '-movflags', '+faststart', str(video)]
    mapping, clips = [], []
    with (out / 'encode.log').open('wb') as log:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=log)
        try:
            for segment in segments:
                first = len(mapping)
                count = math.ceil((segment['end']-segment['start']) / segment['speed'] * FPS) + 1
                plan = [('intro', segment['start'])] * int(segment['intro'] * FPS)
                plan += [('active', min(segment['end'], segment['start']+i*segment['speed']/FPS)) for i in range(count)]
                plan += [('end', segment['end'])] * int(segment['hold'] * FPS)
                for mode, target in plan:
                    index = max(0, bisect.bisect_right(segment['times'], target)-1)
                    frame, latest = render(segment, index, target, mode)
                    process.stdin.write(frame.tobytes())
                    obs = segment['by_frame'][index]
                    mapping.append(dict(video_frame=len(mapping), video_time_s=len(mapping)/FPS,
                        segment=segment['segment'], trial_id=segment['trial_id'], mode=mode,
                        target_sim_s=target, source_frame_index=index, rendering_time_s=obs['rendering_time_s'],
                        observation_id=obs['observation_id'],
                        detection_observation_id=latest['report']['observation_id'] if latest else '',
                        detection_log_sim_s=latest['clock']['sim_time_s'] if latest else ''))
                clips.append(dict(segment=segment['segment'], trial_id=segment['trial_id'],
                    source_directory=str(segment['root']), video_start_s=first/FPS, video_end_s=len(mapping)/FPS,
                    first_video_frame=first, end_video_frame_exclusive=len(mapping), speed=segment['speed'],
                    intro_s=segment['intro'], hold_s=segment['hold'], sim_start_s=segment['start'],
                    sim_end_s=segment['end'], source_files=segment['source_files']))
                print('Rendered', segment['segment'], len(mapping), flush=True)
        finally:
            process.stdin.close()
        if process.wait() != 0:
            raise RuntimeError('Video encoding failed')
    with (out / 'video-frame-map.csv').open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(mapping[0]))
        writer.writeheader()
        writer.writerows(mapping)
    a,b=segments[:2]
    lift=next(e['clock']['sim_time_s'] for e in a['events'] if e['kind']=='NORMAL_ACTION_BEGIN'
              and e.get('arm')=='left' and e.get('operation')=='lift')
    release=next(e['clock']['sim_time_s'] for e in a['events'] if e['kind']=='NORMAL_HAND_COMMAND'
                 and e.get('left')=='open' and e['clock']['sim_time_s']>lift)
    alert=next(e['clock']['sim_time_s'] for e in detection_events(b['events'])
               if e['report']['status']=='ANOMALY')
    held=next(e['clock']['sim_time_s'] for e in b['events'] if e['kind']=='RECOVERY_CHECK'
              and e['report']['status']=='HELD')
    macro=b['record']['macro_execution'][2]
    selections = [('A', lift+.5, '01_A正常提起'), ('A', release+.05, '02_A计划释放'),
                  ('A', a['end'], '03_A完整折叠'),
                  ('B', alert, '04_B观测告警'),
                  ('B', (macro['begin']['sim_time_s']+macro['end']['sim_time_s'])/2, '05_B重抓执行'),
                  ('B', held, '06_B持续持有复检'),
                  ('B', b['end'], '07_B完整折叠'),
                  ('C', segments[2]['end'], '08_C缺条件求助')]
    index_entries = []
    shots = out / '关键截图'
    originals = shots / '原始对应帧'
    originals.mkdir(parents=True, exist_ok=True)
    for key, target, name in selections:
        segment = next(s for s in segments if s['segment'] == key)
        index = max(0, bisect.bisect_right(segment['times'], target)-1)
        raw, annotated = originals / (name+'.png'), shots / (name+'.png')
        Image.fromarray(segment['rgb'][index]).save(raw)
        frame, latest = render(segment, index, target, 'still')
        frame.save(annotated)
        obs = segment['by_frame'][index]
        index_entries.append(dict(file=annotated.relative_to(out).as_posix(),
            raw_file=raw.relative_to(out).as_posix(), trial_id=segment['trial_id'],
            source_frame_index=index, observation_id=obs['observation_id'],
            rendering_time_s=obs['rendering_time_s'], replay_log_sim_s=target,
            raw_sha256=sha(raw), annotated_sha256=sha(annotated)))
    write(out / '截图索引.json', index_entries)
    write(out / 'replay-events.json', [dict(segment=s['segment'], trial_id=s['trial_id'],
        events=s['events'], macro_execution=s['record'].get('macro_execution', [])) for s in segments])
    write(out / 'manifest.json', dict(schema='z3-actual-abc/1',
        video=dict(file=video.name, frames=len(mapping), fps=FPS, duration_s=len(mapping)/FPS,
                   dimensions=list(SIZE), audio=False, bytes=video.stat().st_size, sha256=sha(video)),
        clips=clips, generator_sha256=sha(__file__), shared_renderer_sha256=sha(Path(__file__).with_name('build_pre_z3_evidence.py')),
        score_alignment='Only reports whose logged simulation time is no later than replay time',
        source_frame_alignment='Latest original RGB no later than replay time',
        source_arrays_modified=False, image_transform='Full 640x480 RGB scaled to 960x720',
        experimental_independent_review='pending'))
    for filename in ('build_pre_abc_evidence.py', 'build_pre_z3_evidence.py', 'verify_pre_abc_evidence.py'):
        (out / filename).write_bytes(Path(__file__).with_name(filename).read_bytes())
    figures=''.join(f'<figure><a href="{html.escape(shot["raw_file"])}"><img src="{html.escape(shot["file"])}" alt="{html.escape(Path(shot["file"]).stem)}"></a><figcaption>{html.escape(Path(shot["file"]).stem)}</figcaption></figure>' for shot in index_entries)
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>第三组 A/B/C 实跑证据</title><style>body{max-width:1200px;margin:32px auto;padding:0 20px;background:#101923;color:#eef3f7;font:18px/1.6 system-ui}video,img{width:100%}video{max-height:76vh}a{color:#72d8cd}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(400px,1fr));gap:20px}figure{margin:0}h1{font-size:30px}figcaption{padding:8px}</style>
<h1>第三组 A/B/C 实跑证据</h1><p>A 完成完整折叠且无恢复。B 由 RGB 告警触发五操作，连续持有检查通过后接续并完成。C 缺检测条件时求助。</p>
<p>B 的恢复及接续持有检查使用仿真内部材料片和指尖坐标。原始 RND 分数独立保留。最终区域代理及素材核验已记录，实验独立人工审核待完成。</p>
<video controls preload="metadata" src="Z3_ABC真实检测与恢复.mp4"></video>
<p><a href="manifest.json">视频与源文件清单</a> · <a href="visual-qa.json">素材核验</a> · <a href="video-frame-map.csv">逐帧来源</a> · <a href="截图索引.json">截图索引</a> · <a href="replay-events.json">同试次事件</a></p>
<h2>关键截图</h2><p>点击加注截图查看原始对应帧。</p><div class="grid">'''+figures+'</div></html>'
    (out/'index.html').write_text(page,encoding='utf-8')
    print(json.dumps(dict(video=str(video), frames=len(mapping), duration_s=len(mapping)/FPS)))


if __name__ == '__main__':
    main()
