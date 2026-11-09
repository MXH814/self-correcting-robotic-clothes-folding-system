"""Render a source-mapped offline evidence video; never invent detection scores."""
import argparse
import bisect
import csv
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FPS = 20
SIZE = (1600, 900)
FONT = 'C:/Windows/Fonts/msyh.ttc'
BOLD = 'C:/Windows/Fonts/msyhbd.ttc'
COLORS = {'N': '#6BD8C5', 'R': '#F4BD68', 'C': '#B4A1FF'}
TITLES = {'N': '正常控制采集', 'R': '脚本恢复与接续', 'C': '正式接口 · UNKNOWN 求助'}
LIMITS = {'N': '检测关闭；尚非 A 检测验收', 'R': '固定脚本触发；尚非 B 检测闭环', 'C': '正式 C 实跑；物理静止尚未验收'}


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))


def write(p, data):
    Path(p).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def font(size, bold=False):
    return ImageFont.truetype(BOLD if bold else FONT, size)


def text(draw, xy, value, size=26, fill='#EEF3F7', bold=False, width=None):
    f = font(size, bold)
    x, y = xy
    for para in value.split('\n'):
        line = ''
        for char in para:
            if width and draw.textlength(line + char, font=f) > width:
                draw.text((x, y), line, font=f, fill=fill)
                y += size + 13
                line = char
            else:
                line += char
        draw.text((x, y), line, font=f, fill=fill)
        y += size + 13
    return y


def render(s, index, mode, caption=None):
    key = s['segment']
    rgb, obs = s['rgb'][index], s['by_frame'][index]
    im = Image.new('RGB', SIZE, '#101923')
    d = ImageDraw.Draw(im)
    accent = COLORS[key]
    text(d, (32, 19), '第三组  /  真实仿真证据', 23, '#9FB0C0')
    text(d, (32, 51), f"{['N','R','C'].index(key)+1:02d}   {TITLES[key]}", 34, bold=True)
    text(d, (1016, 30), '独立试次 · 离线剪辑', 25, accent)
    text(d, (1016, 71), LIMITS[key], 23, '#F4D69C')
    im.paste(Image.fromarray(rgb).resize((960, 720), Image.Resampling.LANCZOS), (32, 128))
    text(d, (32, 101), f"原始 RGB 全幅  |  渲染 {obs['rendering_time_s']:.3f} 仿真秒  |  帧 {index}", 18, '#B8C7D5')
    modes = {'intro': '片头静帧 1.5s', 'active': f"活动片段 {s['speed']:g}× 仿真时间",
             'end': f"末帧停留 {s['hold']:g}s · 日志摘要", 'still': '静态备份 · 原图与日志对照'}
    text(d, (1016, 132), modes[mode], 25, accent, bold=True)
    y = text(d, (1016, 184), '本段记录', 23, '#9FB0C0')
    if key == 'N':
        lines = '无故障注入 / 恢复关闭\n正常提起 → 移送 → 计划释放\n保存连续 RGB 与动作反馈'
        result = '未加载检测器\n无分数 / 无阈值 / 无报警结论'
        note = '原始观测中的阶段是控制意图，不是异常真值。'
    elif key == 'R':
        lines = '提前开手后，按固定脚本恢复\n释放 → 退让 → 重抓 → 闭手 → 抬升\n重抓横向偏移 −20 mm'
        result = '五操作共 62 条派发\n接回原 Fold Tops 控制流程'
        note = '最终区域代理 2048/2048；不等于完整质量或自主成功。'
    else:
        lines = '正常提起后，在移送前检查\n真实 RGB → 正式 DetectionRuntime\n检测包缺失 → UNKNOWN'
        result = '求助后新增派发 0 条\n恢复 0 次 / 未继续折叠'
        note = '末帧 RGB 5.950s，求助日志 5.983s。停留画面不是求助后新图像。'
    y = text(d, (1016, y + 3), lines, 26, width=548)
    d.line((1016, y + 17, 1568, y + 17), fill='#334657', width=2)
    y = text(d, (1016, y + 37), '同试次日志摘要（非在线界面）', 22, '#9FB0C0')
    y = text(d, (1016, y + 5), result, 29, accent, bold=True, width=548)
    y = text(d, (1016, y + 17), note, 24, '#C4CED8', width=548)
    if caption:
        text(d, (1016, max(y + 16, 690)), caption, 25, '#FFFFFF', bold=True, width=548)
    d.rectangle((32, 854, 1568, 891), fill='#182636')
    text(d, (46, 856), f"试次 {s['trial_id']}   |   三段独立记录，不是同一次自主闭环", 22)
    return im


def load_segment(clip, key):
    root = Path(clip['source_directory']).resolve()
    trace = read(root / 'observation-trace.json')
    record = read(root / 'full-fold-recovery.json')
    assert trace['trial_id'] == record['trial_id'] == clip['trial_id']
    with np.load(root / 'rgb-frames.npz', allow_pickle=False) as a:
        rgb = a['rgb']
    assert rgb.dtype == np.uint8 and rgb.shape[1:] == (480, 640, 3)
    by_frame = {}
    for obs in trace['observations']:
        by_frame.setdefault(obs['frame_index'], obs)
    times = [by_frame[i]['rendering_time_s'] for i in range(len(rgb))]
    assert all(b > a for a, b in zip(times, times[1:]))
    # Verify source file digests before rendering anything.
    for filename, info in clip.get('source_files', {}).items():
        assert sha(root / filename) == info['sha256'], filename
    source_files = {p.name: {'bytes': p.stat().st_size, 'sha256': sha(p)} for p in root.iterdir()
                    if p.is_file() and (p.suffix in ('.json', '.jsonl') or p.name == 'rgb-frames.npz')}
    return dict(segment=key, root=root, trace=trace, record=record, rgb=rgb, by_frame=by_frame,
                times=times, trial_id=trace['trial_id'], speed=1. if key == 'C' else 2.,
                hold=5. if key == 'C' else 2., start=clip['sim_start_s'], end=times[-1],
                source_files=source_files)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--previous-manifest', type=Path, required=True)
    p.add_argument('--official-c', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--ffmpeg', type=Path, required=True)
    args = p.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    video = out / 'Z3_三段真实记录_正式C更新.mp4'
    if video.exists():
        raise FileExistsError('Use a new output directory or preserve the previous video explicitly')
    clips = read(args.previous_manifest)['clips'][:2]
    ct = read(args.official_c / 'observation-trace.json')
    clips.append(dict(source_directory=str(args.official_c), trial_id=ct['trial_id'],
                      sim_start_s=ct['observations'][0]['rendering_time_s']))
    segments = [load_segment(c, k) for c, k in zip(clips, 'NRC')]
    audit = read(args.official_c.parent.parent / 'official-C-audit-with-source.json')
    assert audit['trial_id'] == ct['trial_id'] and audit['official_runtime_executed']
    assert audit['dispatches_after_refusal'] == audit['recovery_attempts'] == 0
    command = [str(args.ffmpeg), '-hide_banner', '-loglevel', 'warning', '-n', '-f', 'rawvideo',
               '-vcodec', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '1600x900', '-r', str(FPS),
               '-i', '-', '-an', '-c:v', 'libx264', '-preset', 'fast', '-crf', '20',
               '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(video)]
    maps, clip_info, screenshots = [], [], []
    shots = out / '关键截图'
    raw = shots / '原始对应帧'
    raw.mkdir(parents=True, exist_ok=True)
    with (out / 'encode.log').open('wb') as log:
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=log)
        try:
            for s in segments:
                start_frame = len(maps)
                active_count = math.ceil((s['end'] - s['start']) / s['speed'] * FPS) + 1
                plans = [('intro', s['start'])] * 30
                plans += [('active', min(s['end'], s['start'] + i * s['speed'] / FPS)) for i in range(active_count)]
                plans += [('end', s['end'])] * int(FPS * s['hold'])
                for mode, target in plans:
                    index = max(0, bisect.bisect_right(s['times'], target) - 1)
                    im = render(s, index, mode)
                    proc.stdin.write(im.tobytes())
                    obs = s['by_frame'][index]
                    maps.append(dict(video_frame=len(maps), video_time_s=len(maps)/FPS,
                        segment=s['segment'], trial_id=s['trial_id'], mode=mode,
                        target_sim_s=target, source_frame_index=index,
                        rendering_time_s=obs['rendering_time_s'], observation_id=obs['observation_id']))
                clip_info.append(dict(segment=s['segment'], title=TITLES[s['segment']],
                    trial_id=s['trial_id'], source_directory=str(s['root']),
                    video_start_s=start_frame/FPS, video_end_s=len(maps)/FPS,
                    first_video_frame=start_frame, end_video_frame_exclusive=len(maps),
                    sim_start_s=s['start'], sim_end_s=s['end'], speed=s['speed'],
                    introductory_static_s=1.5, final_static_s=s['hold'],
                    source_files=s['source_files'], limitation=LIMITS[s['segment']]))
                print('Rendered', s['segment'], len(maps), flush=True)
        finally:
            proc.stdin.close()
        if proc.wait() != 0:
            raise RuntimeError('FFmpeg failed; inspect encode.log')
    selections = [('N', 58, '01_正常提起', '正常提起：采集时检测关闭'),
                  ('N', 88, '02_计划释放', '控制器计划释放；没有异常报警'),
                  ('R', 79, '03_脚本恢复入口', '脚本进入恢复；非独立检测触发'),
                  ('R', bisect.bisect_right(segments[1]['times'], segments[1]['record']['macro_execution'][-1]['end']['sim_time_s']),
                   '04_五操作后新帧', '宏结束后新渲染帧；持有复检仍待验收'),
                  ('R', len(segments[1]['rgb'])-1, '05_接续最终代理', '区域代理 2048/2048；非完整质量'),
                  ('C', len(segments[2]['rgb'])-1, '06_正式C_UNKNOWN', '正式 C：UNKNOWN → 求助，零新增派发')]
    for key, index, name, caption in selections:
        s = next(s for s in segments if s['segment'] == key)
        rp, ap = raw / (name + '_原帧.png'), shots / (name + '.png')
        Image.fromarray(s['rgb'][index]).save(rp)
        render(s, index, 'still', caption).save(ap)
        obs = s['by_frame'][index]
        screenshots.append(dict(file=ap.relative_to(out).as_posix(), raw_file=rp.relative_to(out).as_posix(),
            trial_id=s['trial_id'], source_frame_index=index, source_rendering_time_s=obs['rendering_time_s'],
            observation_id=obs['observation_id'], description=caption, raw_sha256=sha(rp), annotated_sha256=sha(ap)))
        if name.startswith('04_'):
            finish = s['record']['macro_execution'][-1]['end']['sim_time_s']
            assert obs['rendering_time_s'] > finish
            screenshots[-1].update(macro_finish_sim_s=finish, strictly_after_macro=True)
    write(out / '截图索引.json', screenshots)
    with (out / 'video-frame-map.csv').open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=list(maps[0]))
        w.writeheader()
        w.writerows(maps)
    write(out / 'manifest.json', dict(schema='z3-evidence-video/2', video=dict(file=video.name,
        frames=len(maps), fps=FPS, duration_s=len(maps)/FPS, dimensions=list(SIZE), audio=False,
        bytes=video.stat().st_size, sha256=sha(video)), clips=clip_info, screenshot_index='截图索引.json',
        frame_map='video-frame-map.csv', source_arrays_modified=False,
        image_transform='Full 640x480 RGB scaled to 960x720; no crop or generated simulator content',
        statement='Three separate trials. N/R have no online detector; C official missing-package run. No detection score exists for these clips.',
        generator_sha256=sha(__file__), ffmpeg=str(args.ffmpeg), python=sys.version))
    (out / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    print(json.dumps(dict(frames=len(maps), duration_s=len(maps)/FPS, video=str(video)), ensure_ascii=False))


if __name__ == '__main__':
    main()
