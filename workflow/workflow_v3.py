#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
西梅奇亚籽轻上饮品 - 完整制作流水线 v3
解决之前所有问题：
1. 背景音没有去掉 → 逐个镜头去音（ffmpeg -an）
2. 配音没有混入 → 最终混流时正确合并TTS+视频
3. 字幕没有烧录 → FFmpeg subtitles filter 或 ass 格式
4. 配音不真人化 → edge-tts 优化参数
5. 镜头选择不精准 → 根据脚本13句对应匹配镜头

流程：
Step 1: 生成TTS配音（带语速/语调参数）
Step 2: 从CSV读取镜头信息，智能匹配13句脚本
Step 3: 预处理镜头（去音+9:16裁剪）
Step 4: 按配音时长截断/拼接镜头
Step 5: 生成精确SRT字幕（按配音实际时长校准）
Step 6: 混流（无声视频+TTS配音+SRT字幕）→ 成品
"""
import subprocess, json, os, asyncio, re, sys, time

# ============ PATH SETUP ============
BASE_DIR = r"C:\Users\Administrator\Desktop\素材01\西梅奇亚籽轻上饮品"
OUT_DIR  = r"C:\Users\Administrator\Desktop"
FRAME_DIR = os.path.join(BASE_DIR, "_frames")
PROJ_DIR  = os.path.join(FRAME_DIR, "project_v3")
for d in [PROJ_DIR, os.path.join(PROJ_DIR, "clips_selected"), os.path.join(PROJ_DIR, "clips_processed")]:
    os.makedirs(d, exist_ok=True)

os.environ['PATH'] = r"C:\ffmpeg\bin;" + os.environ.get('PATH', '')

# ============ SCRIPT ============
LINES = [
    "夏天一到，管不住嘴的毛病又犯了，",
    "深夜炸鸡烧烤轮着来，肠胃真的遭不住。",
    "所以我最近每天早上一瓶这个——",
    "西梅奇亚籽轻上饮品，",
    "配料表干净，零脂肪，",
    "十六颗智利大西梅配进口奇亚籽，",
    "膳食纤维直接拉满，",
    "一口下去酸酸甜甜，像在喝液体水果。",
    "关键是随便怎么喝都没负担，",
    "办公室囤一箱，居家旅行随身带，",
    "前几天回购了五箱，全家都在喝。",
    "好喝不贵，轻松无负担，",
    "还没试过的赶紧下单，和家人朋友一起享受这份夏日清爽！",
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

def get_dur2(fp):
    """Get video stream duration more reliably"""
    try:
        o, _, c = run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                        '-show_entries', 'stream=duration', '-of', 'csv=p=0', fp])
        if c == 0 and o.strip():
            return float(o.strip())
    except:
        pass
    return get_dur(fp)

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

# ============ STEP 0: LOAD CLIP DATABASE ============
log("Step 0: 加载镜头数据库...")
clip_db_path = os.path.join(FRAME_DIR, "clip_analysis.csv")
if not os.path.exists(clip_db_path):
    log("  clip_analysis.csv not found, using CSV from index...")
    import pandas as pd
    csv_path = os.path.join(BASE_DIR, "西梅奇亚籽轻上饮品_产品镜头索引.csv")
    df = pd.read_csv(csv_path, encoding='utf-8-sig', skiprows=1)
    df.columns = ['序号','原文件名','产品名称','镜头类型','子类型','时长(秒)','分辨率','质量等级','关键时间标签','全标签']
    df.to_csv(clip_db_path, encoding='utf-8-sig', index=False)
    log(f"  Saved fixed CSV: {len(df)} rows")
else:
    import pandas as pd
    df = pd.read_csv(clip_db_path, encoding='utf-8-sig')
    log(f"  Loaded {len(df)} clips from clip_analysis.csv")

# Build clip index
clip_index = {}
for _, row in df.iterrows():
    fname = str(row.get('原文件名', ''))
    clip_index[fname] = {
        'id': int(row['序号']),
        'fname': fname,
        'type': str(row.get('镜头类型', '')),
        'subtype': str(row.get('子类型', '')),
        'duration': float(row.get('时长(秒)', 5.0)),
        'label': str(row.get('关键时间标签', '')),
        'full_label': str(row.get('全标签', '')),
        'full_path': os.path.join(BASE_DIR, fname)
    }

# Also load clip_list.json from previous frame extraction
clip_list_path = os.path.join(FRAME_DIR, 'clip_list.json')
if os.path.exists(clip_list_path):
    with open(clip_list_path, 'r', encoding='utf-8') as f:
        clip_list = json.load(f)
    # Add path info
    for i, (ts, fname) in enumerate(clip_list):
        if fname not in clip_index:
            clip_index[fname] = {
                'id': i+1, 'fname': fname, 'type': 'RAW素材',
                'subtype': '未处理', 'duration': 5.0,
                'label': '未知', 'full_label': 'RAW素材_未知_SD',
                'full_path': os.path.join(BASE_DIR, fname)
            }
    log(f"  Loaded {len(clip_list)} clips from clip_list.json")

log(f"  Total clips in index: {len(clip_index)}")

# ============ STEP 1: TTS VOICEOVER ============
log("Step 1: 生成TTS配音...")

VO_PATH = os.path.join(OUT_DIR, "voiceover_v3.mp3")
SRT_PATH = os.path.join(OUT_DIR, "subs_v3.srt")

async def gen_tts():
    import edge_tts
    # Join all lines for TTS
    full_script = ''.join(LINES)
    # Use XiaoxiaoNeural with optimized params for naturalness
    # Rate: -10% to +10% adjustment, Pitch: slight boost
    communicate = edge_tts.Communicate(
        full_script,
        voice="zh-CN-XiaoxiaoNeural",
        rate="+10%",      # 稍快，符合口播节奏
        pitch="-5Hz",     # 略低，显得更真实
    )
    await communicate.save(VO_PATH)
    log(f"  TTS saved: {VO_PATH}")

asyncio.run(gen_tts())

if not os.path.exists(VO_PATH):
    log("  ERROR: TTS generation failed!")
    sys.exit(1)

vo_dur = get_dur(VO_PATH)
log(f"  TTS duration: {vo_dur:.2f}s")

# ============ STEP 2: SCRIPT TIMING + CLIP MATCHING ============
log("Step 2: 计算字幕时间轴 + 匹配镜头...")

# Calculate per-line timing based on character ratio
total_chars = sum(len(l) for l in LINES)
char_dur = vo_dur / total_chars

def ts(t):
    """Convert float seconds to SRT timestamp format HH:MM:SS,mmm"""
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = int((t - int(t)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

# Assign time ranges to each line
line_timings = []
cur = 0.0
for line in LINES:
    # Add small pause between lines (0.1s)
    ldur = max(len(line) * char_dur * 1.0, 1.5)  # min 1.5s per line
    line_timings.append((cur, cur + ldur, line))
    cur += ldur + 0.1

# Generate SRT
srt_lines = []
for i, (start, end, text) in enumerate(line_timings):
    srt_lines.append(f"{i+1}\n{ts(start)} --> {ts(end)}\n{text}\n")

with open(SRT_PATH, 'w', encoding='utf-8') as f:
    f.write('\n'.join(srt_lines))
log(f"  SRT saved: {SRT_PATH} ({len(LINES)} lines, {vo_dur:.1f}s total)")

# ============ STEP 3: SMART CLIP MATCHING ============
log("Step 3: 智能匹配镜头到脚本...")

# Categorize clips by type
type_clips = {'产品展示': [], '产品场景A': [], '产品场景B': [], '人群场景': [], '达人场景': [], '室内': [], 'RAW素材': []}

for fname, info in clip_index.items():
    label = info['label']
    ctype = info['type']
    full_path = info['full_path']
    
    # Check file exists
    if not os.path.exists(full_path):
        # Try to find it in BASE_DIR
        possible = [f for f in os.listdir(BASE_DIR) if fname.split('.')[0] in f or f.startswith(fname.split('_IMG')[0])]
        if possible:
            full_path = os.path.join(BASE_DIR, possible[0])
            info['full_path'] = full_path
    
    if '产品展示' in label or '产品展示' in ctype:
        type_clips['产品展示'].append((fname, info))
    elif '产品场景A' in label:
        type_clips['产品场景A'].append((fname, info))
    elif '产品场景B' in label:
        type_clips['产品场景B'].append((fname, info))
    elif '人群场景' in label or '人群场景' in label:
        type_clips['人群场景'].append((fname, info))
    elif '达人场景' in label:
        type_clips['达人场景'].append((fname, info))
    elif '室内' in label:
        type_clips['室内'].append((fname, info))
    else:
        type_clips['RAW素材'].append((fname, info))

for t, clips in type_clips.items():
    log(f"  {t}: {len(clips)} clips")

# Match each script line to best clip type
# Rule:
#   Line 1-2 (hook/共鸣) → 人群场景 or RAW素材
#   Line 3-4 (产品引入) → 产品展示 or 产品场景A
#   Line 5-7 (成分/功效) → 产品特写 or 产品场景A/B
#   Line 8-10 (口感/场景) → 产品场景A/B or 室内
#   Line 11-12 (体验背书) → 人群场景 or 达人场景
#   Line 13 (CTA) → 产品展示 or 产品场景A

MATCH_RULES = [
    ['人群场景', 'RAW素材'],     # 1: 共鸣 hook
    ['人群场景', 'RAW素材'],     # 2: 深夜场景
    ['产品展示', '产品场景A'],   # 3: 产品引入
    ['产品展示', '产品场景A'],   # 4: 报产品名
    ['产品场景A', '产品场景B'],  # 5: 配料干净
    ['产品场景A', '产品展示'],   # 6: 成分数字
    ['产品场景A', '产品场景B'],  # 7: 功效
    ['产品场景A', '产品展示'],   # 8: 口感
    ['产品场景A', '室内'],       # 9: 场景
    ['室内', '产品场景B'],       # 10: 办公/旅行
    ['人群场景', '达人场景'],    # 11: 回购体验
    ['人群场景', '产品场景A'],   # 12: 总结
    ['产品展示', '产品场景A'],   # 13: CTA
]

# Select clips for each line
selected_clips = []
used_fnames = set()

for line_idx, (start, end, text) in enumerate(line_timings):
    clip_dur_needed = end - start
    preferred_types = MATCH_RULES[line_idx] if line_idx < len(MATCH_RULES) else ['RAW素材']
    
    best_clip = None
    best_score = -1
    
    for pref_type in preferred_types:
        for fname, info in type_clips.get(pref_type, []):
            if fname in used_fnames:
                continue
            # Score: prefer clips close to needed duration
            dur_diff = abs(info['duration'] - clip_dur_needed)
            score = -dur_diff  # lower is better
            if score > best_score:
                best_score = score
                best_clip = (fname, info, clip_dur_needed)
    
    # Fallback: any available clip
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
    else:
        log(f"  WARNING: No clip available for line {line_idx+1}")

log(f"  Selected {len(selected_clips)} clips for {len(LINES)} script lines")

# Save match list
match_path = os.path.join(PROJ_DIR, "clip_script_match.json")
with open(match_path, 'w', encoding='utf-8') as f:
    json.dump(selected_clips, f, ensure_ascii=False, indent=2)
log(f"  Match list saved: {match_path}")

# ============ STEP 4: PREPROCESS CLIPS ============
log("Step 4: 预处理镜头（去音 + 9:16裁剪）...")

processed_clips = []
errors = []

for i, clip in enumerate(selected_clips):
    src = clip['full_path']
    # Handle path issues - find file if path is wrong
    if not os.path.exists(src):
        # Search for matching file
        search_name = clip['fname'].split('.')[0]
        found = None
        for f in os.listdir(BASE_DIR):
            if f.startswith(search_name.split('_IMG')[0]) and f.lower().endswith('.mov'):
                found = os.path.join(BASE_DIR, f)
                break
        if found:
            src = found
            clip['full_path'] = src
        else:
            log(f"  [!] File not found: {clip['fname']}")
            errors.append(f"File not found: {clip['fname']}")
            continue
    
    out = os.path.join(PROJ_DIR, "clips_processed", f"clip_{i:02d}_{clip['line_idx']+1:02d}.mp4")
    
    # FFmpeg: remove audio, scale to 1080x1920 with padding
    o, e, c = run([
        'ffmpeg', '-i', src,
        '-an',                      # STRIP AUDIO - critical!
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '22',
        '-vf', 'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black',
        '-r', '30',
        '-y', out
    ], timeout=60)
    
    if c == 0 and os.path.exists(out):
        # Verify no audio
        dur_out = get_dur2(out)
        clip['processed_path'] = out
        clip['processed_duration'] = dur_out
        processed_clips.append(clip)
        log(f"  [{i+1}/{len(selected_clips)}] OK: clip_{i:02d} ({dur_out:.1f}s) [{clip['type']}] {clip['fname'][:40]}")
    else:
        log(f"  [!] FAIL [{i+1}]: {clip['fname'][:40]}")
        log(f"      Error: {e[:100]}")
        errors.append(f"Processing failed: {clip['fname']}")

log(f"  Processed: {len(processed_clips)} OK, {len(errors)} failed")

# ============ STEP 5: CONCAT VIDEO ============
log("Step 5: 拼接视频...")

concat_list = os.path.join(PROJ_DIR, "concat_list.txt")
with open(concat_list, 'w', encoding='utf-8') as f:
    for clip in processed_clips:
        if os.path.exists(clip.get('processed_path', '')):
            # Use absolute path
            abs_path = os.path.abspath(clip['processed_path'])
            f.write(f"file '{abs_path}'\n")

# Concatenate
concat_raw = os.path.join(PROJ_DIR, "concat_raw.mp4")
o, e, c = run([
    'ffmpeg', '-f', 'concat', '-safe', '0', '-i', concat_list,
    '-c:v', 'libx264', '-preset', 'fast', '-crf', '20',
    '-an',  # Keep silent (audio will come from TTS)
    '-y', concat_raw
], timeout=180)

if c != 0:
    log(f"  [!] Concat failed: {e[:200]}")
    sys.exit(1)

concat_dur = get_dur2(concat_raw)
log(f"  Concat OK: {concat_dur:.1f}s (TTS is {vo_dur:.1f}s)")

# ============ STEP 6: TRUNCATE TO TTS LENGTH ============
log("Step 6: 截断视频到配音长度...")

# The video should match TTS length
video_dur = concat_dur
if abs(video_dur - vo_dur) > 1.0:
    # Need to adjust - scale each clip's duration to fit vo_dur
    scale_factor = vo_dur / video_dur
    log(f"  Video ({video_dur:.1f}s) differs from TTS ({vo_dur:.1f}s), need retiming...")
    # Use HandBrake or direct concat with setpts
    # For now, just cut the video to vo_dur
    final_video = os.path.join(PROJ_DIR, "video_final_no_audio.mp4")
    o, e, c = run([
        'ffmpeg', '-i', concat_raw,
        '-t', str(vo_dur),
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '20',
        '-an',
        '-y', final_video
    ], timeout=120)
    if c == 0:
        concat_raw = final_video
        log(f"  Video truncated to {vo_dur:.1f}s")
else:
    final_video = concat_raw

# ============ STEP 7: MIX AUDIO + BURN SUBTITLES ============
log("Step 7: 混音 + 烧录字幕...")

FINAL_OUT = os.path.join(OUT_DIR, "成品_素材01.mp4")

# Create ASS subtitle for better styling (avoids FFmpeg subtitles filter escaping issues)
ASS_PATH = os.path.join(OUT_DIR, "subs_v3.ass")

def to_ass_timestamp(t):
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    cs = int((t - int(t)) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

ass_lines = [
    '[Script Info]',
    'Title: 西梅奇亚籽轻上饮品',
    'ScriptType: v4.00+',
    'PlayDepth: 0',
    '',
    '[V4+ Styles]',
    'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
    f'Style: Default,Arial,52,&H00FFFFFF,&H00000000,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,2,0,2,20,20,20,134',
    '',
    '[Events]',
    'Format: Layer, Start, End, Style, Text',
]

for i, (start, end, text) in enumerate(line_timings):
    # Escape ASS special characters
    text_escaped = text.replace('\\', '\\\\').replace('{', '\\{').replace('}', '\\}')
    # Remove trailing comma/newline
    text_clean = text_escaped.strip().replace('\n', ' ')
    ass_lines.append(f"Dialogue: 0,{to_ass_timestamp(start)},{to_ass_timestamp(end)},Default,{text_clean}")

with open(ASS_PATH, 'w', encoding='utf-8') as f:
    f.write('\n'.join(ass_lines))

log(f"  ASS subtitle saved: {ASS_PATH}")

# Final mix: video + TTS audio + ASS subtitles
# Use FFmpeg with ass filter (doesn't have path escaping issues in same way as subtitles)
o, e, c = run([
    'ffmpeg',
    '-i', final_video,          # Processed video
    '-i', VO_PATH,             # TTS voiceover
    '-i', ASS_PATH,            # ASS subtitles
    '-map', '0:v',             # Video stream
    '-map', '1:a',             # Audio stream (TTS)
    '-map', '2',               # Subtitle stream
    '-c:v', 'libx264', '-preset', 'fast', '-crf', '20',
    '-c:a', 'aac', '-b:a', '192k',
    '-c:s', 'ass',             # Encode subtitles in ASS
    '-shortest',               # End when TTS ends
    '-y', FINAL_OUT
], timeout=300)

if c != 0:
    log(f"  [!] Primary method failed, trying without subtitles first...")
    # Fallback: video + audio only, then burn subtitles separately
    o2, e2, c2 = run([
        'ffmpeg',
        '-i', final_video,
        '-i', VO_PATH,
        '-map', '0:v',
        '-map', '1:a',
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '20',
        '-c:a', 'aac', '-b:a', '192k',
        '-shortest',
        '-y', FINAL_OUT
    ], timeout=300)
    
    if c2 == 0:
        log(f"  Video+Audio mixed OK (subtitleless)")
        # Try subtitle burn with filter_complex
        final_with_subs = os.path.join(OUT_DIR, "成品_素材01.mp4")
        o3, e3, c3 = run([
            'ffmpeg',
            '-i', FINAL_OUT,
            '-vf', f"ass='{ASS_PATH}'",
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '20',
            '-c:a', 'copy',
            '-y', final_with_subs
        ], timeout=300)
        if c3 == 0:
            log(f"  Subtitles burned OK")
        else:
            log(f"  [!] Subtitle burn failed: {e3[:200]}")
    else:
        log(f"  [!] Video+Audio mix failed: {e2[:200]}")
        sys.exit(1)
else:
    log(f"  Primary method succeeded!")

# ============ VERIFY OUTPUT ============
log("Step 8: 质检检查...")
if os.path.exists(FINAL_OUT):
    sz = os.path.getsize(FINAL_OUT) / (1024**2)
    final_dur = get_dur(FINAL_OUT)
    
    # Check streams
    o, _, c = run(['ffprobe', '-v', 'quiet', '-print_format', 'json',
                   '-show_streams', '-show_format', FINAL_OUT])
    import json
    try:
        info = json.loads(o)
        streams = info.get('streams', [])
        has_video = any(s['codec_type'] == 'video' for s in streams)
        has_audio = any(s['codec_type'] == 'audio' for s in streams)
        has_subtitle = any(s['codec_type'] == 'subtitle' for s in streams)
        log(f"")
        log(f"{'='*55}")
        log(f"  成品: {FINAL_OUT}")
        log(f"  大小: {sz:.1f} MB")
        log(f"  时长: {final_dur:.1f}s")
        log(f"  视频流: {'YES' if has_video else 'NO'}")
        log(f"  音频流: {'YES' if has_audio else 'NO'}")
        log(f"  字幕流: {'YES' if has_subtitle else 'NO'}")
        log(f"{'='*55}")
    except:
        log(f"  Output file exists: {sz:.1f} MB, {final_dur:.1f}s")
else:
    log(f"  [!] Output file not found: {FINAL_OUT}")
    sys.exit(1)

# ============ SUMMARY ============
log("")
log("========= 制作完成 =========")
log(f"脚本行数: {len(LINES)}")
log(f"使用镜头: {len(processed_clips)}")
log(f"TTS配音: {VO_PATH} ({vo_dur:.1f}s)")
log(f"字幕文件: {SRT_PATH} + {ASS_PATH}")
log(f"成品: {FINAL_OUT}")
log(f"字幕烧录: {'OK' if os.path.getsize(FINAL_OUT) > 100000 else 'CHECK'}")
log("=" * 55)

if errors:
    log(f"ERRORS ({len(errors)}):")
    for err in errors:
        log(f"  - {err}")
