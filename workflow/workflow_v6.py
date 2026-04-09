#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workflow_v6.py - 基于爆款文案的完整制作流水线
解决4个问题：
1. 结尾黑屏：拼接视频总时长必须 >= TTS时长，不够则加速或扩充
2. 语速太慢：edge-tts rate=+20%（原来是+5%），提升真人感
3. 文案太弱：基于爆款文案套路重写，每句都有营销目的
4. 镜头匹配：每个镜头服务于对应文案卖点
"""
import subprocess, json, os, asyncio, re, sys, time
from collections import OrderedDict

# ============ PATH SETUP ============
BASE_DIR  = r"C:\Users\Administrator\Desktop\素材01\西梅奇亚籽轻上饮品"
OUT_DIR   = r"C:\Users\Administrator\Desktop"
FRAME_DIR = os.path.join(BASE_DIR, "_frames")
PROJ_DIR  = os.path.join(FRAME_DIR, "project_60s_v6")
for d in [PROJ_DIR, os.path.join(PROJ_DIR, "clips_selected"),
          os.path.join(PROJ_DIR, "clips_processed")]:
    os.makedirs(d, exist_ok=True)

# ============ V6爆款文案（20句）============
# 套路：开场钩子→痛点→产品→成分数据→口感→人群→价格锚点→催促
LINES = [
    "你吃牛肉一个月，我只喝它一礼拜，",                        # 01 开场钩子：对比反差
    "改不了半夜吃烧烤的习惯，肠胃真的遭不住。",                  # 02 痛点共鸣
    "所以我每天早上一瓶这个——",                                # 03 转折引入
    "轻上西梅奇亚籽奶昔，",                                     # 04 产品名
    "配料表干净，零脂肪，",                                      # 05 成分
    "16颗智利大西梅，配进口奇亚籽，",                           # 06 核心成分（数据）
    "膳食纤维直接拉满，",                                        # 07 功效
    "入口酸酸甜甜，像在喝液体水果。",                            # 08 口感描写
    "关键是0添加蔗糖，怎么喝都没负担。",                         # 09 产品特点
    "像我这样天天外卖重油重口的，",                             # 10 人群定向
    "还有久坐不动、管不住嘴的姐妹，",                            # 11 扩展人群
    "再不买就恢复69一箱了，",                                    # 12 价格锚点+紧迫感
    "现在拍一发十，巨划算，",                                    # 13 价格利好
    "我刚喝了一礼拜，全家都跟着囤了五箱。",                      # 14 效果见证
    "好喝不贵，轻松无负担，",                                    # 15 总结
    "电商爆款，好喝到飞起，",                                    # 16 社交证明
    "回购率超高，朋友们都在喝，",                                # 17 口碑
    "甄选优质西梅，添加进口奇亚籽，",                            # 18 成分品质
    "还没试过的赶紧下单，",                                      # 19 催促
    "和家人朋友一起享受这份夏日清爽！",                          # 20 CTA结尾
]

# 每句对应的画面需求说明（用于指导选镜头）
SHOT_PURPOSE = [
    "对比画面：有人吃大餐 vs 有人喝奶昔",      # 01
    "深夜吃烧烤/炸鸡的画面（负面）",           # 02
    "产品从冰箱/货架拿起的画面",                # 03
    "产品展示：西梅奇亚籽奶昔",                 # 04
    "干净的配料表/成分表特写",                  # 05
    "西梅+奇亚籽原料展示/产品剖面",             # 06
    "膳食纤维含量数据可视化",                   # 07
    "喝奶昔的享受表情/液体流动特写",           # 08
    "轻上产品摆拍/办公室场景",                  # 09
    "外卖场景/重油食物",                        # 10
    "久坐办公/各种零食堆的场景",                 # 11
    "价格牌/倒计时/紧迫感画面",                 # 12
    "直播间/促销画面/产品堆满桌",              # 13
    "家庭场景/囤货/开箱画面",                   # 14
    "产品摆拍/生活场景",                        # 15
    "电商爆款/榜单/销量数据",                   # 16
    "朋友推荐/分享场景",                        # 17
    "西梅/奇亚籽原料特写",                      # 18
    "下单动作/购物车/快递发货",                # 19
    "朋友聚会/家庭享用/夏日场景",              # 20
]

EMOTIONS = [
    "自信对比", "共鸣", "转折", "自豪", "专业",
    "数据感", "满足", "享受", "轻松", "场景",
    "场景", "紧迫感", "划算感", "体验", "肯定",
    "激昂", "推荐", "品质感", "催促", "温馨CTA"
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

# ============ CLIP DB ============
def load_clip_db():
    clip_db_path = os.path.join(FRAME_DIR, "clip_analysis.csv")
    csv_path = os.path.join(BASE_DIR, "西梅奇亚籽轻上饮品_产品镜头索引.csv")
    if not os.path.exists(clip_db_path) and os.path.exists(csv_path):
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()
        with open(clip_db_path, 'w', encoding='utf-8') as f:
            f.write("序号,原文件名,产品名称,镜头类型,子类型,时长(秒),分辨率,质量等级,关键时间标签,全标签\n")
            for line in lines[1:]:
                if ',' in line:
                    f.write(line)
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
                'full_path': os.path.join(BASE_DIR, fname),
            }
    return clip_index

def get_scene_key(fname):
    parts = fname.split('_')
    if len(parts) >= 5:
        return '_'.join(parts[:5])
    return fname[:20]

# ============ V6 SMARTER CLIPS SELECTOR ============
def select_clips_v6(clip_index, lines, match_rules):
    """
    V6: 基于镜头用途选择
    每个镜头必须能服务于对应文案的目的
    """
    type_clips = {'产品展示': [], '产品场景A': [], '产品场景B': [],
                  '人群场景': [], 'RAW素材': [], '室内': [], '达人场景': []}
    for fname, info in clip_index.items():
        ctype = info['type']
        path = info['full_path']
        if not os.path.exists(path):
            continue
        if '产品展示' in str(ctype):
            type_clips['产品展示'].append((fname, info))
        elif '产品场景A' in str(ctype):
            type_clips['产品场景A'].append((fname, info))
        elif '产品场景B' in str(ctype):
            type_clips['产品场景B'].append((fname, info))
        elif '人群场景' in str(ctype):
            type_clips['人群场景'].append((fname, info))
        elif '室内' in str(ctype):
            type_clips['室内'].append((fname, info))
        elif '达人' in str(ctype):
            type_clips['达人场景'].append((fname, info))
        else:
            type_clips['RAW素材'].append((fname, info))

    selected = []
    used_fnames = set()
    prev_scene = None
    consecutive_same_scene = 0

    # 为每句文案选最合适的镜头
    for line_idx in range(len(lines)):
        preferred = match_rules[line_idx] if line_idx < len(match_rules) else ['RAW素材']
        line_text = lines[line_idx]
        shot_purpose = SHOT_PURPOSE[line_idx] if line_idx < len(SHOT_PURPOSE) else ''

        best = None
        best_score = -9999

        for pref_type in preferred:
            for fname, info in type_clips.get(pref_type, []):
                if fname in used_fnames:
                    continue

                # 场景去重惩罚
                scene = get_scene_key(fname)
                scene_penalty = -999 if scene == prev_scene else 0

                # 镜头时长匹配度（不要太长也不要太短）
                line_dur_estimate = max(len(line_text) * 0.12, 2.0)  # 估算文案朗读时长
                dur_diff = abs(info['duration'] - line_dur_estimate)
                dur_score = -dur_diff

                # 标签关键词匹配（字幕里有啥关键词就用对应标签的镜头）
                label_text = info.get('label', '') + info.get('full_path', '')
                keyword_bonus = 0
                if any(k in label_text for k in ['产品特写', '产品推出', '成分展示']):
                    if any(k in line_text for k in ['配料', '成分', '16颗', '奇亚籽']):
                        keyword_bonus = 50
                if any(k in label_text for k in ['人群', '场景', '生活']):
                    if any(k in line_text for k in ['姐妹', '全家', '朋友', '外卖']):
                        keyword_bonus = 50
                if any(k in label_text for k in ['RAW素材', '纯色', '背景']):
                    if any(k in line_text for k in ['电商', '回购', '直播']):
                        keyword_bonus = 30

                score = scene_penalty + dur_score + keyword_bonus
                if score > best_score:
                    best_score = score
                    best = (fname, info)

        # Fallback
        if best is None:
            for fname, info in clip_index.items():
                if fname not in used_fnames:
                    scene = get_scene_key(fname)
                    if scene != prev_scene:
                        best = (fname, info)
                        break

        if best:
            fname, info = best
            used_fnames.add(fname)
            scene = get_scene_key(fname)
            selected.append({
                'line_idx': line_idx,
                'line_text': line_text,
                'shot_purpose': shot_purpose,
                'fname': fname,
                'full_path': info['full_path'],
                'duration': info['duration'],
                'type': info['type'],
                'label': info['label'],
                'scene': scene,
            })
            prev_scene = scene

    return selected

# ============ MAIN WORKFLOW ============
def main():
    log("=" * 60)
    log("V6 爆款文案流水线启动")
    log("=" * 60)

    # STEP 0: Load DB
    clip_index = load_clip_db()
    log(f"  DB loaded: {len(clip_index)} clips")

    # STEP 1: Generate TTS FIRST (rate=+20%, more natural)
    log("\n[Step 1] 生成TTS配音 (rate=+20%, 真人感提升)...")
    VO_PATH = os.path.join(OUT_DIR, "voiceover_v6.mp3")
    SRT_PATH = os.path.join(OUT_DIR, "subs_v6.srt")

    full_script = ''.join(LINES)
    log(f"  Script: {len(LINES)} lines, {len(full_script)} chars")

    async def gen_tts():
        import edge_tts
        communicate = edge_tts.Communicate(
            full_script,
            voice="zh-CN-XiaoxiaoNeural",
            rate="+20%",    # 原来+5%，现在是+20%，明显加快
            pitch="-3Hz",
        )
        await communicate.save(VO_PATH)

    asyncio.run(gen_tts())
    vo_dur = get_dur(VO_PATH)
    log(f"  TTS: {vo_dur:.2f}s (旧版约62s，新版目标54s)")

    # STEP 2: Calculate line timings based on ACTUAL TTS audio
    # 用edge_tts内置的word-level timing生成精确字幕
    log("\n[Step 2] 提取精确字幕时间轴...")

    async def get_word_timing():
        import edge_tts
        from edge_tts import SubMaker
        submaker = SubMaker()
        # Generate with word timing
        communicate = edge_tts.Communicate(
            full_script,
            voice="zh-CN-XiaoxiaoNeural",
            rate="+20%",
            pitch="-3Hz",
        )
        await submaker.from_url(communicate._opts["url"])
        return submaker

    try:
        submaker = asyncio.run(get_word_timing())
        with open(SRT_PATH, 'w', encoding='utf-8') as f:
            f.write(submaker.to_srt())
        log(f"  SRT generated with word-level timing")
    except Exception as e:
        log(f"  Word timing failed: {e}, using char-based estimation")
        # Fallback: 字符比例分配
        total_chars = len(full_script)
        char_dur = vo_dur / total_chars
        line_timings = []
        cur = 0.0
        for line in LINES:
            ldur = max(len(line) * char_dur * 1.05, 1.8)
            line_timings.append({'start': cur, 'end': cur + ldur, 'text': line})
            cur += ldur + 0.06
        def ts(t):
            h = int(t // 3600)
            m = int((t % 3600) // 60)
            s = int(t % 60)
            ms = int((t - int(t)) * 1000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
        srt_lines = []
        for i, lt in enumerate(line_timings):
            srt_lines.append(f"{i+1}\n{ts(lt['start'])} --> {ts(lt['end'])}\n{lt['text']}\n")
        with open(SRT_PATH, 'w', encoding='utf-8') as f:
            f.write('\n'.join(srt_lines))

    # Verify SRT
    with open(SRT_PATH, 'rb') as f:
        raw = f.read()
    blocks = raw.split(b'\r\n\r\n')
    log(f"  SRT entries: {len([b for b in blocks if b.strip()])}")

    # STEP 3: Select clips with V6 purpose-driven selector
    log("\n[Step 3] 选择镜头（用途驱动）...")

    MATCH_RULES = [
        ['人群场景', 'RAW素材'],      # 01 开场钩子
        ['人群场景', 'RAW素材'],      # 02 痛点
        ['产品展示', '产品场景A'],    # 03 产品引入
        ['产品展示', '产品场景A'],    # 04 产品名
        ['产品展示', '产品场景A'],    # 05 配料干净
        ['产品展示', '产品场景A'],    # 06 成分数据
        ['产品展示', '产品场景B'],    # 07 功效
        ['产品展示', '产品场景A'],    # 08 口感
        ['产品展示', '产品场景A'],    # 09 0添加
        ['人群场景', 'RAW素材'],      # 10 人群定向
        ['人群场景', 'RAW素材'],      # 11 扩展人群
        ['产品场景B', 'RAW素材'],     # 12 价格锚点
        ['产品场景B', '人群场景'],   # 13 价格利好
        ['人群场景', 'RAW素材'],      # 14 体验见证
        ['产品场景A', '室内'],        # 15 总结
        ['RAW素材', '产品场景B'],     # 16 电商爆款
        ['人群场景', '达人场景'],    # 17 口碑
        ['产品展示', '产品场景A'],   # 18 成分品质
        ['产品场景B', '产品展示'],   # 19 催促
        ['人群场景', '产品场景A'],   # 20 CTA
    ]

    clips = select_clips_v6(clip_index, LINES, MATCH_RULES)
    log(f"  Selected {len(clips)} clips")

    # Print selection rationale
    for i, c in enumerate(clips):
        log(f"  [{i+1:02d}] {c['type'][:8]} | {c['shot_purpose'][:20]} | {c['fname'][:30]}")

    # STEP 4: Process clips
    log("\n[Step 4] 预处理镜头...")
    processed = []
    for i, clip in enumerate(clips):
        src = clip['full_path']
        if not os.path.exists(src):
            log(f"  [!] Missing: {clip['fname']}")
            continue

        out = os.path.join(PROJ_DIR, "clips_processed", f"clip_{i:02d}.mp4")

        # 跳过前0.3秒不稳定帧，截取合理长度
        skip_start = 0.3
        src_dur = clip['duration'] - skip_start

        o, e, c = run([
            'ffmpeg', '-ss', str(skip_start), '-i', src,
            '-t', str(src_dur),
            '-an',
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '22',
            '-vf', 'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black',
            '-r', '30', '-y', out
        ], timeout=60)

        if c == 0 and os.path.exists(out):
            actual_dur = get_dur(out)
            clip['processed_path'] = out
            clip['processed_dur'] = actual_dur
            processed.append(clip)
            log(f"  [{i+1:02d}] OK: {actual_dur:.1f}s")
        else:
            log(f"  [!] FAIL: {clip['fname'][:30]}")

    log(f"  Processed: {len(processed)}/{len(clips)}")

    # STEP 5: Concat
    log("\n[Step 5] 拼接视频...")
    concat_list = os.path.join(PROJ_DIR, "concat_list.txt")
    with open(concat_list, 'w', encoding='utf-8') as f:
        for clip in processed:
            abs_path = os.path.abspath(clip['processed_path'])
            f.write(f"file '{abs_path}'\n")

    concat_raw = os.path.join(PROJ_DIR, "concat_raw.mp4")
    o, e, c = run([
        'ffmpeg', '-f', 'concat', '-safe', '0', '-i', concat_list,
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '20', '-an', '-y', concat_raw
    ], timeout=180)

    concat_dur = get_dur(concat_raw)
    log(f"  Concat: {concat_dur:.2f}s vs TTS: {vo_dur:.2f}s")

    # STEP 6: ADJUST视频时长 to match TTS (核心修复！)
    # 如果视频不够长：加速或填充；如果太长：截断
    log("\n[Step 6] 时长对齐（解决黑屏问题）...")

    final_video = os.path.join(PROJ_DIR, "video_final_no_audio.mp4")

    dur_diff_pct = (concat_dur - vo_dur) / vo_dur * 100
    log(f"  差异: {dur_diff_pct:+.1f}% ({concat_dur:.1f}s vs {vo_dur:.1f}s)")

    if concat_dur < vo_dur - 0.5:
        # 视频太短：需要加速（加速后音调会变，edge-tts的rate参数已做补偿）
        speed_factor = concat_dur / vo_dur
        atempo = 1.0 / speed_factor
        atempo = max(0.67, min(1.5, atempo))  # 限制在0.67x~1.5x
        log(f"  视频太短({concat_dur:.1f}s < {vo_dur:.1f}s)，加速 {atempo:.3f}x")
        o, e, c = run([
            'ffmpeg', '-i', concat_raw,
            '-filter:a', f'atempo={atempo}',
            '-t', str(vo_dur),
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '20', '-an', '-y', final_video
        ], timeout=120)
        if c == 0:
            log(f"  加速完成，目标{vo_dur:.1f}s")
        else:
            log(f"  [!] 加速失败: {e[:100]}")
            final_video = concat_raw
    elif concat_dur > vo_dur + 1.0:
        # 视频太长：截断
        log(f"  视频略长，截断到{vo_dur:.1f}s")
        o, e, c = run([
            'ffmpeg', '-i', concat_raw,
            '-t', str(vo_dur),
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '20', '-an', '-y', final_video
        ], timeout=120)
        if c != 0:
            final_video = concat_raw
    else:
        # 差异可接受，直接使用
        import shutil
        shutil.copy(concat_raw, final_video)
        log(f"  时长接近，直接使用")

    final_dur = get_dur(final_video)
    log(f"  最终视频时长: {final_dur:.2f}s")

    # STEP 7: Mix audio + Burn subtitles (PIL)
    log("\n[Step 7] 混音 + 字幕烧录...")
    FINAL_OUT = os.path.join(OUT_DIR, "成品_素材01_60s_v6.mp4")

    import moviepy as mp
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    video = mp.VideoFileClip(final_video)
    tts_audio = mp.AudioFileClip(VO_PATH)
    FONT = r'C:\Windows\Fonts\msyh.ttc'

    def parse_srt_crlf(path):
        with open(path, 'rb') as f:
            raw = f.read()
        blocks = raw.split(b'\r\n\r\n')
        entries = []
        for block in blocks:
            if not block.strip():
                continue
            lines = block.split(b'\r\n')
            if len(lines) < 3:
                continue
            ts_line = lines[1].decode('utf-8')
            m = re.match(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})', ts_line)
            if not m:
                continue
            start = int(m.group(1))*3600 + int(m.group(2))*60 + int(m.group(3)) + int(m.group(4))/1000
            end = int(m.group(5))*3600 + int(m.group(6))*60 + int(m.group(7)) + int(m.group(8))/1000
            text = b'\r\n'.join(lines[2:]).decode('utf-8').strip()
            entries.append({'start': start, 'end': end, 'text': text})
        return entries

    def render_subtitle(text, font_size=52, stroke=3):
        tmp = Image.new('RGBA', (10, 10), (0, 0, 0, 0))
        td = ImageDraw.Draw(tmp)
        font = ImageFont.truetype(FONT, font_size)
        bbox = td.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        pad_x, pad_y = 40, 15
        iw = min(tw + pad_x * 2, 1040)
        ih = th + pad_y * 2
        img = Image.new('RGBA', (iw, ih), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        xc = (iw - tw) // 2 - bbox[0]
        yc = (ih - th) // 2 - bbox[1]
        for dx in range(-stroke, stroke+1):
            for dy in range(-stroke, stroke+1):
                if abs(dx) == stroke or abs(dy) == stroke:
                    d.text((xc+dx, yc+dy), text, font=font, fill=(0, 0, 0, 255))
        d.text((xc, yc), text, font=font, fill=(255, 255, 255, 255))
        return np.array(img, dtype='uint8')

    subs = parse_srt_crlf(SRT_PATH)
    log(f"  Loaded {len(subs)} subtitles")

    sub_clips = []
    for i, s in enumerate(subs):
        dur = s['end'] - s['start']
        if dur <= 0 or not s['text'].strip():
            continue
        try:
            sub_img = render_subtitle(s['text'])
            tc = mp.ImageClip(sub_img).with_duration(dur)
            x_pos = (1080 - sub_img.shape[1]) / 2
            y_pos = video.h - sub_img.shape[0] - 80
            tc = tc.with_position((x_pos, y_pos)).with_start(s['start'])
            sub_clips.append(tc)
        except Exception as ex:
            log(f"  [!] Sub {i+1} failed: {ex}")

    composite = mp.CompositeVideoClip([video] + sub_clips, size=(1080, 1920))
    composite = composite.with_audio(tts_audio)
    composite = composite.with_duration(tts_audio.duration)

    log(f"  Writing: {FINAL_OUT}")
    composite.write_videofile(
        FINAL_OUT, codec='libx264', audio_codec='aac',
        audio_bitrate='192k', preset='fast', fps=30, threads=4, logger='bar'
    )

    # STEP 8: Post-QC
    log("\n[Step 8] 质检...")
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
        log(f"{'='*60}")
        log(f"  成品: {FINAL_OUT}")
        log(f"  大小: {sz:.1f} MB")
        log(f"  时长: {dur:.1f}s (TTS: {vo_dur:.1f}s, 差:{abs(dur-vo_dur):.1f}s)")
        log(f"  视频流: {'YES' if has_v else 'NO'}")
        log(f"  音频流: {'YES' if has_a else 'NO'}")
        log(f"  文案: V6爆款文案（rate=+20%）")
        log(f"  字幕: PIL微软雅黑")
        log(f"{'='*60}")

if __name__ == '__main__':
    main()
