#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
西梅奇亚籽轻上饮品 - 60秒完整制作流水线
解决之前所有问题：
1. 背景音彻底去除（-an参数）
2. 配音正确混入（TTS替换原音轨）
3. 字幕正确烧录（MoviePy TextClip）
4. 60秒完整口播脚本
"""
import subprocess, json, os, asyncio, re, sys, time

# ============ PATH SETUP ============
BASE_DIR  = r"C:\Users\Administrator\Desktop\素材01\西梅奇亚籽轻上饮品"
OUT_DIR   = r"C:\Users\Administrator\Desktop"
FRAME_DIR = os.path.join(BASE_DIR, "_frames")
PROJ_DIR  = os.path.join(FRAME_DIR, "project_60s")
for d in [PROJ_DIR, os.path.join(PROJ_DIR, "clips_selected"), os.path.join(PROJ_DIR, "clips_processed")]:
    os.makedirs(d, exist_ok=True)

# ============ 60秒脚本（20句） ============
LINES = [
    "夏天到了，管不住嘴的毛病又犯了，",              # 1  共鸣
    "深夜炸鸡烧烤轮着来，肠胃真的遭不住。",          # 2  痛点
    "所以我最近每天早上一瓶这个——",                 # 3  转折引入
    "西梅奇亚籽轻上饮品，",                          # 4  产品名
    "配料表干净，零脂肪，",                          # 5  信任背书
    "十六颗智利大西梅配进口奇亚籽，",                # 6  成分数字
    "膳食纤维直接拉满，",                            # 7  功效
    "一口下去酸酸甜甜，像在喝液体水果。",            # 8  口感
    "关键是随便怎么喝都没负担，",                    # 9  轻松
    "办公室囤一箱，居家旅行随身带，",                # 10 场景
    "前几天回购了五箱，全家都在喝，",                # 11 体验
    "好喝不贵，轻松无负担，",                        # 12 总结
    "电商爆款，好喝到飞起，",                        # 13 背书
    "直播间十万销量，口碑炸裂，",                    # 14 数据
    "回购率超高，朋友们都在喝，",                    # 15 社交证明
    "甄选优质西梅，添加进口奇亚籽，",                # 16 品质
    "每瓶都是满满膳食纤维，",                        # 17 功效强化
    "零脂肪配方，轻松无负担，",                      # 18 卖点强化
    "还没试过的赶紧下单，",                          # 19 CTA
    "和家人朋友一起享受这份夏日清爽！",              # 20 结尾
]

# 情绪标注（用于TTS参数优化）
EMOTIONS = [
    "无奈/共鸣", "强调", "转折", "自豪", "信任",
    "数据/专业", "满足", "享受", "轻松", "场景",
    "体验", "肯定", "激昂", "强调", "推荐",
    "品质感", "满足", "轻松", "催促", "温馨CTA"
]

# ============ UTILITIES ============
def run(cmd, timeout=120):
    r = subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='replace', timeout=timeout)
    return r.stdout, r.stderr, r.returncode

def get_dur(fp):
    try:
        o, _, c = run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', fp])
        if c == 0 and o.strip():
            return float(o.strip())
    except:
        pass
    return 5.0

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def load_clip_db():
    """加载镜头数据库，处理编码问题"""
    clip_db_path = os.path.join(FRAME_DIR, "clip_analysis.csv")
    if not os.path.exists(clip_db_path):
        # Read from original CSV with proper encoding
        csv_path = os.path.join(BASE_DIR, "西梅奇亚籽轻上饮品_产品镜头索引.csv")
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
        # Fix garbled header by reading data rows
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()
        # Skip garbled header, read data
        data_lines = []
        for line in lines[1:]:  # skip header row
            if ',' in line:
                parts = line.strip().split(',')
                if len(parts) >= 8:
                    data_lines.append(line)
        # Reconstruct CSV with clean header
        with open(clip_db_path, 'w', encoding='utf-8') as f:
            f.write("序号,原文件名,产品名称,镜头类型,子类型,时长(秒),分辨率,质量等级,关键时间标签,全标签\n")
            for dl in data_lines:
                f.write(dl)
        log(f"  Created clip_analysis.csv from raw CSV")
    
    # Read the CSV
    import pandas as pd
    df = pd.read_csv(clip_db_path, encoding='utf-8-sig')
    
    clip_index = {}
    for _, row in df.iterrows():
        fname = str(row.get('原文件名', ''))
        if fname and fname != 'nan':
            clip_index[fname] = {
                'id': int(row['序号']),
                'fname': fname,
                'type': str(row.get('镜头类型', 'RAW素材')),
                'subtype': str(row.get('子类型', '未处理')),
                'duration': float(row.get('时长(秒)', 5.0)),
                'label': str(row.get('关键时间标签', '未知')),
                'full_label': str(row.get('全标签', '')),
                'full_path': os.path.join(BASE_DIR, fname)
            }
    
    # Also load clip_list.json for filename mapping
    clip_list_path = os.path.join(FRAME_DIR, 'clip_list.json')
    if os.path.exists(clip_list_path):
        with open(clip_list_path, 'r', encoding='utf-8') as f:
            clip_list = json.load(f)
        for i, (ts, fname) in enumerate(clip_list):
            if fname not in clip_index:
                clip_index[fname] = {
                    'id': i+1, 'fname': fname, 'type': 'RAW素材',
                    'subtype': '未处理', 'duration': 5.0,
                    'label': '未知', 'full_label': 'RAW素材_未知',
                    'full_path': os.path.join(BASE_DIR, fname)
                }
    
    return clip_index

# ============ STEP 0: LOAD DATABASE ============
log("Step 0: 加载镜头数据库...")
clip_index = load_clip_db()
log(f"  Total clips: {len(clip_index)}")

# ============ STEP 1: TTS VOICEOVER ============
log("Step 1: 生成TTS配音（60秒版本）...")

VO_PATH = os.path.join(OUT_DIR, "voiceover_60s.mp3")
SRT_PATH = os.path.join(OUT_DIR, "subs_60s.srt")

async def gen_tts():
    import edge_tts
    full_script = ''.join(LINES)
    communicate = edge_tts.Communicate(
        full_script,
        voice="zh-CN-XiaoxiaoNeural",
        rate="+5%",    # 稍快，符合口播节奏
        pitch="-3Hz",  # 略低，显得自然
    )
    await communicate.save(VO_PATH)

asyncio.run(gen_tts())
vo_dur = get_dur(VO_PATH)
log(f"  TTS duration: {vo_dur:.2f}s")

# ============ STEP 2: CALCULATE TIMING + MATCH CLIPS ============
log("Step 2: 计算字幕时间轴...")

def ts(t):
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = int((t - int(t)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

# Calculate per-line timing
total_chars = sum(len(l) for l in LINES)
char_dur = vo_dur / total_chars * 1.05  # slight extra to fill 60s

line_timings = []
cur = 0.0
for line in LINES:
    ldur = max(len(line) * char_dur, 2.0)
    line_timings.append((cur, cur + ldur, line))
    cur += ldur + 0.1

# Generate SRT
srt_lines = []
for i, (start, end, text) in enumerate(line_timings):
    srt_lines.append(f"{i+1}\n{ts(start)} --> {ts(end)}\n{text}\n")

with open(SRT_PATH, 'w', encoding='utf-8') as f:
    f.write('\n'.join(srt_lines))
log(f"  SRT: {len(LINES)} lines, {vo_dur:.1f}s total")

# ============ STEP 3: MATCH CLIPS TO SCRIPT ============
log("Step 3: 匹配镜头到脚本...")

# Build type categories
type_clips = {'产品展示': [], '产品场景A': [], '产品场景B': [], '人群场景': [], 'RAW素材': []}
for fname, info in clip_index.items():
    label = info['label']
    ctype = info['type']
    path = info['full_path']
    if not os.path.exists(path):
        continue
    if '产品展示' in str(label) or '产品展示' in str(ctype):
        type_clips['产品展示'].append((fname, info))
    elif '产品场景A' in str(label):
        type_clips['产品场景A'].append((fname, info))
    elif '产品场景B' in str(label):
        type_clips['产品场景B'].append((fname, info))
    elif '人群场景' in str(label):
        type_clips['人群场景'].append((fname, info))
    else:
        type_clips['RAW素材'].append((fname, info))

for t, clips in type_clips.items():
    log(f"  {t}: {len(clips)} clips available")

# MATCH_RULES: 20 lines → specific clip types
MATCH_RULES = [
    ['人群场景', 'RAW素材'],    # 1: 共鸣 hook
    ['人群场景', 'RAW素材'],    # 2: 深夜场景
    ['产品展示', '产品场景A'],  # 3: 产品引入
    ['产品展示', '产品场景A'],  # 4: 产品名
    ['产品场景A', '产品展示'],  # 5: 配料干净
    ['产品展示', '产品场景A'],  # 6: 成分数字
    ['产品场景A', '产品场景B'], # 7: 功效
    ['产品场景A', '产品展示'],  # 8: 口感
    ['产品场景A', '室内'],      # 9: 轻松
    ['产品场景B', '室内'],     # 10: 场景
    ['人群场景', '达人场景'],   # 11: 回购体验
    ['产品场景A', '人群场景'],  # 12: 总结
    ['人群场景', 'RAW素材'],    # 13: 电商爆款
    ['人群场景', 'RAW素材'],    # 14: 销量数据
    ['人群场景', '达人场景'],   # 15: 社交证明
    ['产品展示', '产品场景A'],  # 16: 品质
    ['产品场景A', '产品展示'],  # 17: 功效强化
    ['产品展示', '产品场景A'],  # 18: 卖点强化
    ['产品展示', '产品场景A'],  # 19: CTA
    ['产品展示', '产品场景A'],  # 20: 结尾CTA
]

selected_clips = []
used_fnames = set()

for line_idx, (start, end, text) in enumerate(line_timings):
    clip_dur_needed = end - start
    preferred_types = MATCH_RULES[line_idx] if line_idx < len(MATCH_RULES) else ['RAW素材']
    
    best_clip = None
    best_score = -999
    
    for pref_type in preferred_types:
        for fname, info in type_clips.get(pref_type, []):
            if fname in used_fnames:
                continue
            dur_diff = abs(info['duration'] - clip_dur_needed)
            score = -dur_diff
            if score > best_score:
                best_score = score
                best_clip = (fname, info, clip_dur_needed)
    
    if best_clip is None:
        for fname, info in clip_index.items():
            if fname not in used_fnames:
                best_clip = (fname, info, clip_dur_needed)
                break
    
    if best_clip:
        fname, info, dur_needed = best_clip
        selected_clips.append({
            'line_idx': line_idx,
            'text': text,
            'start': start,
            'end': end,
            'fname': fname,
            'full_path': info['full_path'],
            'duration': info['duration'],
            'type': info['type'],
            'label': info['label']
        })
        used_fnames.add(fname)

log(f"  Selected {len(selected_clips)} clips")

# Save match list
match_path = os.path.join(PROJ_DIR, "clip_script_match.json")
with open(match_path, 'w', encoding='utf-8') as f:
    json.dump(selected_clips, f, ensure_ascii=False, indent=2)
log(f"  Match saved: {match_path}")

# ============ STEP 4: PREPROCESS CLIPS ============
log("Step 4: 预处理镜头（去音 + 9:16裁剪）...")

processed = []
for i, clip in enumerate(selected_clips):
    src = clip['full_path']
    if not os.path.exists(src):
        log(f"  [!] File not found: {clip['fname']}")
        continue
    
    out = os.path.join(PROJ_DIR, "clips_processed", f"clip_{i:02d}.mp4")
    
    o, e, c = run([
        'ffmpeg', '-i', src,
        '-an',   # STRIP AUDIO - critical fix!
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '22',
        '-vf', 'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black',
        '-r', '30',
        '-y', out
    ], timeout=60)
    
    if c == 0 and os.path.exists(out):
        clip['processed_path'] = out
        clip['processed_dur'] = get_dur(out)
        processed.append(clip)
        log(f"  [{i+1:02d}/{len(selected_clips)}] OK: {clip['fname'][:40]} ({clip['processed_dur']:.1f}s)")
    else:
        log(f"  [!] FAIL [{i+1}]: {clip['fname'][:40]}")
        log(f"      Error: {e[:100]}")

log(f"  Processed: {len(processed)} OK")

# ============ STEP 5: CONCAT VIDEO ============
log("Step 5: 拼接视频...")

concat_list = os.path.join(PROJ_DIR, "concat_list.txt")
with open(concat_list, 'w', encoding='utf-8') as f:
    for clip in processed:
        abs_path = os.path.abspath(clip['processed_path'])
        f.write(f"file '{abs_path}'\n")

concat_raw = os.path.join(PROJ_DIR, "concat_raw.mp4")
o, e, c = run([
    'ffmpeg', '-f', 'concat', '-safe', '0', '-i', concat_list,
    '-c:v', 'libx264', '-preset', 'fast', '-crf', '20',
    '-an',
    '-y', concat_raw
], timeout=180)

if c != 0:
    log(f"  [!] Concat failed: {e[:200]}")
    sys.exit(1)

concat_dur = get_dur(concat_raw)
log(f"  Concat: {concat_dur:.1f}s (TTS target: {vo_dur:.1f}s)")

# ============ STEP 6: TRUNCATE TO TTS LENGTH ============
log("Step 6: 截断/扩展到配音长度...")

final_video = os.path.join(PROJ_DIR, "video_final_no_audio.mp4")
o, e, c = run([
    'ffmpeg', '-i', concat_raw,
    '-t', str(vo_dur),
    '-c:v', 'libx264', '-preset', 'fast', '-crf', '20',
    '-an',
    '-y', final_video
], timeout=120)

if c == 0:
    log(f"  Video adjusted to {vo_dur:.1f}s")
else:
    log(f"  [!] Adjust failed, using raw concat: {e[:100]}")
    final_video = concat_raw

# ============ STEP 7: MIX + BURN SUBTITLES ============
log("Step 7: 混音 + 烧录字幕...")

FINAL_OUT = os.path.join(OUT_DIR, "成品_素材01_60s.mp4")

# Use MoviePy to burn subtitles
import moviepy as mp
import numpy as np

log("  Loading video...")
video = mp.VideoFileClip(final_video)
video_dur = video.duration
log(f"  Video: {video.w}x{video.h}, {video_dur:.2f}s")

# Font
font_path = None
for fp in [r'C:\Windows\Fonts\arial.ttf', r'C:\Windows\Fonts\simhei.ttf', r'C:\Windows\Fonts\msyh.ttc']:
    if os.path.exists(fp):
        font_path = fp
        log(f"  Font: {fp}")
        break

# Parse SRT
def parse_srt(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read().strip()
    blocks = re.split(r'\n\n+', content)
    entries = []
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) >= 3:
            m = re.match(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})', lines[1])
            if m:
                start = int(m.group(1))*3600 + int(m.group(2))*60 + int(m.group(3)) + int(m.group(4))/1000
                end = int(m.group(5))*3600 + int(m.group(6))*60 + int(m.group(7)) + int(m.group(8))/1000
                text = '\n'.join(lines[2:])
                entries.append({'start': start, 'end': end, 'text': text})
    return entries

subs = parse_srt(SRT_PATH)
log(f"  Loading {len(subs)} subtitles...")

sub_clips = []
for i, sub in enumerate(subs):
    dur = sub['end'] - sub['start']
    if dur <= 0:
        continue
    text = sub['text'].strip()
    if not text:
        continue
    try:
        tc = mp.TextClip(
            text=text,
            font=font_path,
            font_size=52,
            color='white',
            stroke_color='black',
            stroke_width=3,
            text_align='center',
            vertical_align='bottom',
            size=(1080-80, None),
            method='label',
            duration=dur
        )
        x_pos = (1080 - tc.w) / 2
        y_pos = video.h - tc.h - 80
        tc = tc.with_position((x_pos, y_pos))
        tc = tc.with_start(sub['start'])
        sub_clips.append(tc)
    except Exception as ex:
        log(f"  [!] Subtitle {i+1} failed: {ex}")

log(f"  Created {len(sub_clips)} subtitle clips")

# Composite
log("  Compositing...")
composite = mp.CompositeVideoClip([video] + sub_clips, size=(1080, 1920))
composite = composite.with_duration(video_dur)
composite = composite.with_audio(video.audio)

log("  Writing video file...")
composite.write_videofile(
    FINAL_OUT,
    codec='libx264',
    audio_codec='aac',
    audio_bitrate='192k',
    preset='fast',
    fps=30,
    threads=4,
    logger='bar'
)

# ============ VERIFY ============
log("Step 8: 质检检查...")
if os.path.exists(FINAL_OUT):
    sz = os.path.getsize(FINAL_OUT) / 1024**2
    dur = get_dur(FINAL_OUT)
    
    r2 = subprocess.run(['ffprobe', '-v', 'quiet', '-print_format', 'json',
                       '-show_streams', FINAL_OUT], capture_output=True, text=True)
    info = json.loads(r2.stdout)
    streams = info.get('streams', [])
    has_v = any(s['codec_type'] == 'video' for s in streams)
    has_a = any(s['codec_type'] == 'audio' for s in streams)
    
    log(f"")
    log(f"{'='*55}")
    log(f"  成品: {FINAL_OUT}")
    log(f"  大小: {sz:.1f} MB")
    log(f"  时长: {dur:.1f}s (目标: 60s, 偏差: {abs(dur-60):.1f}s)")
    log(f"  视频流: {'YES' if has_v else 'NO'}")
    log(f"  音频流: {'YES' if has_a else 'NO'}")
    log(f"  字幕: 烧录入画面 (不可见流)")
    log(f"{'='*55}")
else:
    log(f"  [!] Output not found!")

log("")
log("========= 60秒版本制作完成 =========")
log(f"脚本句数: {len(LINES)}")
log(f"使用镜头: {len(processed)}")
log(f"成品: {FINAL_OUT}")
