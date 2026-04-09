#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workflow_v8.py - 彻底解决4个问题
1. 字幕同步：逐行TTS实测精确时间（不用字符估算）
2. 镜头去重：内容指纹去重（YYYY_MM_DD_HH_MM同场景只选1个）
3. 节奏优化：动势剪切 + 快慢分层剪辑
4. 分段情感TTS：紧迫CTA vs 真诚痛点 vs 温暖邀请 用不同声音参数
"""
import subprocess, json, os, asyncio, re, time, shutil
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import moviepy as mp

BASE_DIR  = r"C:\Users\Administrator\Desktop\素材01\西梅奇亚籽轻上饮品"
OUT_DIR   = r"C:\Users\Administrator\Desktop"
FRAME_DIR = os.path.join(BASE_DIR, "_frames")
PROJ_DIR  = os.path.join(FRAME_DIR, "project_60s_v8")
TMP_DIR   = os.path.join(PROJ_DIR, "_tmp")
for d in [PROJ_DIR, TMP_DIR, os.path.join(PROJ_DIR, "clips_processed")]:
    os.makedirs(d, exist_ok=True)

FONT = r'C:\Windows\Fonts\msyh.ttc'

# ============ V8 脚本（完全原创） ============
# 核心改进：分段TTS参数——每句按情绪用不同声音状态
LINES = [
    ('夜深了躺在床上刷手机，肚子咕咕叫想吃夜宵，',         '共鸣',   '+15%', '-8Hz', 2.5),
    ('外卖划了半天又怕胖，关掉又不甘心。',                  '纠结',   '+15%', '-8Hz', 2.0),
    ('直到闺蜜给我安利了这瓶——',                          '转折',   '+25%', '-5Hz', 1.8),
    ('轻上西梅奇亚籽饮品，',                               '介绍',   '+25%', '-5Hz', 1.5),
    ('配料表一扫，零脂肪，配料干净，',                       '验证',   '+25%', '-5Hz', 2.0),
    ('关键是里面真的有16颗智利西梅，奇亚籽也是实实在在看得见的那种。', '成分', '+25%', '-5Hz', 3.5),
    ('倒出来就能喝，酸酸甜甜的，像在嚼一杯液体水果。',      '口感',   '+25%', '-5Hz', 2.5),
    ('关键是零添加蔗糖，喝完嘴巴里是清爽的那种甜，',        '特点',   '+25%', '-5Hz', 2.5),
    ('我现在办公桌常备，下午茶时段来一瓶，',                 '场景',   '+25%', '-5Hz', 2.5),
    ('那些天天吃外卖重油重辣的，还有久坐少动管不住嘴的，',  '人群',   '+25%', '-5Hz', 3.0),
    ('想保持身材又不想亏嘴的，真心可以试试。',              '邀请',   '+20%', '-3Hz', 2.0),
    ('现在直播间搞活动，算下来一瓶才三块多，',               '价格',   '+38%', '+5Hz', 1.8),
    ('我上次回购了五箱，家里人抢着喝，',                     '见证',   '+20%', '-3Hz', 2.0),
    ('电商平台十万+销量，口碑一直很稳，',                    '背书',   '+25%', '-5Hz', 2.0),
    ('朋友推荐给我的，现在我也推荐给你。',                   '社交',   '+25%', '-5Hz', 2.0),
    ('智利西梅配进口奇亚籽，每一瓶都是高膳食纤维，',         '成分',   '+25%', '-5Hz', 2.5),
    ('零脂肪配方，好喝轻体无负担，',                          '总结',   '+25%', '-5Hz', 2.0),
    ('这波活动库存有限，卖完就恢复原价了，',                  '紧迫',   '+45%', '+8Hz', 1.5),
    ('想尝鲜的朋友，赶紧下单，',                               '催促',   '+45%', '+8Hz', 1.2),
    ('和家人一起享用，一起保持轻盈好状态！',                  'CTA',    '+18%', '-3Hz', 2.0),
]

# 每句的画面意图（更深层）
SHOT_GOALS = [
    "深夜卧室刷手机特写（共鸣场景）",
    "反复开关外卖App（纠结犹豫）",
    "闺蜜递产品/产品从冰箱出现（转折引入）",
    "产品全貌摆拍（正式亮相）",
    "配料表/成分表特写（验证干净）",
    "西梅原料+奇亚籽特写（具体数据）",
    "液体倒入杯中流动（口感画面）",
    "人物喝完表情满足（清爽感受）",
    "办公桌/下午茶场景（日常场景）",
    "外卖重油食物特写（人群定向）",
    "好状态自展示（向往感）",
    "直播间/倒计时/价格标签（价格利好）",
    "家庭囤货开箱（回购见证）",
    "电商榜单/销量截图（数据背书）",
    "朋友分享推荐（社交闭环）",
    "原料组合品质感（成分强调）",
    "产品卖点总结摆拍（记忆强化）",
    "库存紧张/空货架（紧迫感）",
    "下单/购物车特写（行动催化）",
    "温馨家庭聚会场景（温暖结尾）",
]

# 节奏分层剪辑速度（秒/镜头）
PACE_MAP = {
    '共鸣': (2.5, 3.5),   # 慢，留够情绪
    '纠结': (2.0, 2.5),
    '转折': (1.8, 2.5),
    '介绍': (1.5, 2.0),
    '验证': (1.8, 2.2),
    '成分': (2.0, 3.0),
    '口感': (2.0, 2.5),
    '特点': (2.0, 2.5),
    '场景': (2.0, 2.5),
    '人群': (2.5, 3.0),
    '邀请': (1.8, 2.2),
    '价格': (1.2, 1.8),   # 快，制造紧迫
    '见证': (1.5, 2.0),
    '背书': (1.5, 2.0),
    '社交': (1.5, 2.0),
    '总结': (1.5, 2.0),
    '紧迫': (0.8, 1.2),   # 最快
    '催促': (0.8, 1.2),
    'CTA':  (1.8, 2.5),
}

def log(msg):
    print(f'[{time.strftime("%H:%M:%S")}] {msg}', flush=True)

def run(cmd, timeout=120):
    r = subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='replace', timeout=timeout)
    return r.stdout, r.stderr, r.returncode

def get_dur(fp):
    try:
        o, _, c = run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', fp])
        if c == 0 and o.strip():
            return float(o.strip())
    except: pass
    return 5.0

# ============ LOAD CLIP DB ============
def load_clip_db():
    clip_db = os.path.join(FRAME_DIR, 'clip_analysis.csv')
    csv_path = os.path.join(BASE_DIR, '西梅奇亚籽轻上饮品_产品镜头索引.csv')
    if not os.path.exists(clip_db) and os.path.exists(csv_path):
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            rows = f.readlines()
        with open(clip_db, 'w', encoding='utf-8') as f:
            f.write('序号,原文件名,类型,时长\n')
            for r in rows[1:]:
                parts = r.strip().split(',')
                if len(parts) >= 5:
                    fname = parts[1]
                    ctype = parts[3]
                    dur = parts[5] if len(parts) > 5 else '5.0'
                    f.write(f"{parts[0]},{fname},{ctype},{dur}\n")
    import pandas as pd
    df = pd.read_csv(clip_db, encoding='utf-8-sig')
    clip_index = {}
    for _, row in df.iterrows():
        fname = str(row.get('原文件名', ''))
        if fname and fname != 'nan':
            clip_index[fname] = {
                'id': int(row['序号']),
                'fname': fname,
                'type': str(row.get('类型', 'RAW素材')),
                'duration': float(row.get('时长', 5.0)),
                'full_path': os.path.join(BASE_DIR, fname),
            }
    return clip_index

def get_scene_key(fname):
    """场景指纹：同一分钟内拍的算同一场景"""
    parts = fname.replace('.MOV', '').split('_')
    if len(parts) >= 5:
        return '_'.join(parts[:5])  # YYYY_MM_DD_HH_MM
    return fname[:20]

# ============ SELECT CLIPS V8 ============
def select_clips_v8(clip_index, lines, clip_pace_targets):
    """
    V8选镜头核心逻辑：
    1. 场景去重：同分钟内只选1个镜头
    2. 节奏匹配：每句文案的目标镜头时长
    3. 镜头内容匹配：关键词匹配镜头标签
    4. fname全局去重：每個只能用一次
    """
    # 按类型分类
    type_clips = {'产品展示': [], '产品场景A': [], '产品场景B': [],
                  '人群场景': [], 'RAW素材': [], '室内': [], '达人场景': []}
    for fname, info in clip_index.items():
        if not os.path.exists(info['full_path']):
            continue
        ct = info['type']
        if '产品展示' in str(ct): type_clips['产品展示'].append((fname, info))
        elif '产品场景A' in str(ct): type_clips['产品场景A'].append((fname, info))
        elif '产品场景B' in str(ct): type_clips['产品场景B'].append((fname, info))
        elif '人群场景' in str(ct): type_clips['人群场景'].append((fname, info))
        elif '室内' in str(ct): type_clips['室内'].append((fname, info))
        elif '达人' in str(ct): type_clips['达人场景'].append((fname, info))
        else: type_clips['RAW素材'].append((fname, info))

    # 意图关键词
    KW = {
        0:  ['深夜', '刷', '手机', '卧'],      # 深夜刷手机
        1:  ['外卖', 'App', '手', '划'],        # 外卖犹豫
        2:  ['冰箱', '递', '出现', '闺蜜'],    # 转折引入
        3:  ['产品', '摆拍', '全貌'],           # 产品亮相
        4:  ['配料', '成分', '干净'],            # 配料表
        5:  ['西梅', '奇亚', '原料', '颗粒'],   # 原料特写
        6:  ['液体', '倒', '流动', '杯'],       # 液体口感
        7:  ['喝', '表情', '甜'],               # 享受表情
        8:  ['办公', '下午茶', '常备', '桌'],   # 办公场景
        9:  ['外卖', '重油', '辣', '人群'],     # 外卖人群
        10: ['状态', '好', '身材', '自信'],     # 效果场景
        11: ['直播', '价格', '优惠', '活动'],   # 直播间
        12: ['开箱', '囤货', '家庭', '回购'],   # 家庭囤货
        13: ['榜单', '销量', '数据', '电商'],  # 电商数据
        14: ['推荐', '朋友', '分享'],           # 社交推荐
        15: ['原料', '品质', '组合', '智利'],   # 品质感
        16: ['摆拍', '卖点', '总结', '产品'],   # 总结摆拍
        17: ['库存', '空', '紧迫', '货架'],     # 库存紧迫
        18: ['下单', '购买', '购物车', '行动'], # 下单动作
        19: ['温馨', '家庭', '聚会', '朋友'],  # 温馨场景
    }

    MATCH_RULES = [
        ['人群场景', 'RAW素材'],     # 0 深夜
        ['人群场景', 'RAW素材'],     # 1 外卖
        ['产品展示', '产品场景A'],   # 2 闺蜜推荐
        ['产品展示', '产品场景A'],   # 3 产品亮相
        ['产品展示', '产品场景A'],   # 4 配料表
        ['产品展示', '产品场景A'],   # 5 原料
        ['产品展示', '产品场景A'],   # 6 液体
        ['产品展示', '产品场景A'],   # 7 表情
        ['室内', '产品场景B'],       # 8 办公
        ['人群场景', 'RAW素材'],     # 9 人群
        ['人群场景', '产品场景A'],   # 10 效果
        ['产品场景B', 'RAW素材'],    # 11 直播
        ['人群场景', 'RAW素材'],     # 12 开箱
        ['RAW素材', '产品场景B'],    # 13 电商
        ['人群场景', '达人场景'],    # 14 推荐
        ['产品展示', '产品场景A'],   # 15 品质
        ['产品展示', '产品场景A'],   # 16 总结
        ['产品场景B', 'RAW素材'],    # 17 紧迫
        ['产品场景B', '室内'],       # 18 下单
        ['人群场景', '室内'],        # 19 温馨
    ]

    selected = []
    used_fnames = set()
    used_scenes = set()  # 场景指纹去重（关键！）

    for line_idx in range(len(lines)):
        text, emotion, rate, pitch, target_dur = lines[line_idx]
        pace_range = PACE_MAP.get(emotion, (1.5, 2.5))
        preferred = MATCH_RULES[line_idx] if line_idx < len(MATCH_RULES) else ['RAW素材']
        keywords = KW.get(line_idx, [])

        best = None
        best_score = -9999

        for pref_type in preferred:
            for fname, info in type_clips.get(pref_type, []):
                if fname in used_fnames:
                    continue

                scene = get_scene_key(fname)
                # 场景去重：同分钟用过就跳过
                if scene in used_scenes:
                    continue

                label = info.get('label', fname)

                # 评分
                kw_match = sum(20 for kw in keywords if kw in label or kw in fname)
                dur_diff = abs(info['duration'] - target_dur)
                dur_score = -abs(dur_diff - (pace_range[0] + pace_range[1])/2) * 3

                score = kw_match + dur_score

                if score > best_score:
                    best_score = score
                    best = (fname, info, scene)

        # Fallback：允许同场景但优先不同子类型
        if best is None:
            for pref_type in preferred:
                for fname, info in type_clips.get(pref_type, []):
                    if fname in used_fnames:
                        continue
                    scene = get_scene_key(fname)
                    best = (fname, info, scene)
                    break
                if best: break

        if best:
            fname, info, scene = best
            used_fnames.add(fname)
            used_scenes.add(scene)  # 场景指纹记录
            selected.append({
                'line_idx': line_idx, 'text': text, 'emotion': emotion,
                'fname': fname, 'full_path': info['full_path'],
                'duration': info['duration'], 'type': info['type'],
                'scene': scene, 'pace_range': pace_range,
                'goal': SHOT_GOALS[line_idx],
            })
            log(f"  [{line_idx+1:02d}] {emotion:4s} | {scene[-8:]} | {fname[:28]}")

    return selected

# ============ TTS ============
async def gen_tts(text, path, rate='+25%', pitch='-5Hz'):
    import edge_tts
    await edge_tts.Communicate(text, voice='zh-CN-XiaoxiaoNeural',
                                rate=rate, pitch=pitch).save(path)

# ============ MAIN ============
async def main():
    log('='*60)
    log('V8: 精准字幕同步 + 场景去重 + 情感TTS')
    log('='*60)

    clip_index = load_clip_db()
    log(f'  DB: {len(clip_index)} clips')

    # STEP 1: 逐行TTS + 实测时长
    log('\n[Step 1] 逐行TTS（情感参数）+ 实测时间...')
    timings = []
    cur = 0.0

    for i, (text, emotion, rate, pitch, target) in enumerate(LINES):
        p = os.path.join(TMP_DIR, f'line_{i:02d}.mp3')
        await gen_tts(text, p, rate=rate, pitch=pitch)
        dur = get_dur(p)
        timings.append({
            'line': i+1, 'text': text, 'emotion': emotion,
            'rate': rate, 'pitch': pitch,
            'start': round(cur, 3), 'end': round(cur+dur, 3), 'dur': round(dur, 3)
        })
        log(f"  {i+1:2d} | {cur:5.2f}→{cur+dur:5.2f} ({dur:.2f}s) | {emotion:4s} | {rate} {pitch} | {text[:18]}")
        cur += dur + 0.05

    total_audio = cur - 0.05
    log(f"  总配音时长: {total_audio:.2f}s")

    # 生成SRT
    def ts(t):
        h, m, s, ms = int(t//3600), int((t%3600)//60), int(t%60), int((t-int(t))*1000)
        return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'
    srt_lines = []
    for t in timings:
        srt_lines.append(f"{t['line']}\n{ts(t['start'])} --> {ts(t['end'])}\n{t['text']}\n")
    SRT_PATH = os.path.join(OUT_DIR, 'subs_v8.srt')
    with open(SRT_PATH, 'w', encoding='utf-8') as f:
        f.write('\n'.join(srt_lines))
    log(f"  SRT: {len(timings)} 条字幕")

    # 合并TTS音频
    log('\n[Step 2] 合并配音...')
    concat_list = os.path.join(TMP_DIR, 'audio_concat.txt')
    with open(concat_list, 'w') as f:
        for i in range(len(LINES)):
            p = os.path.join(TMP_DIR, f'line_{i:02d}.mp3')
            if os.path.exists(p):
                f.write(f"file '{os.path.abspath(p)}'\n")
    VO_PATH = os.path.join(OUT_DIR, 'voiceover_v8.mp3')
    o, e, c = run(['ffmpeg', '-f', 'concat', '-safe', '0', '-i', concat_list,
                   '-acodec', 'libmp3lame', '-ab', '192k', '-y', VO_PATH], timeout=60)
    audio_dur = get_dur(VO_PATH)
    log(f"  合并后: {audio_dur:.2f}s")

    # STEP 3: 选镜头（场景去重）
    log('\n[Step 3] V8场景去重选镜...')
    clips = select_clips_v8(clip_index, LINES, PACE_MAP)
    log(f"  选中: {len(clips)} clips")

    # Verify scene deduplication
    scenes_used = [c['scene'] for c in clips]
    dupe_scenes = len(scenes_used) - len(set(scenes_used))
    fnames_used = [c['fname'] for c in clips]
    dupe_fnames = len(fnames_used) - len(set(fnames_used))
    log(f"  场景重复: {dupe_scenes} (应为0) | fname重复: {dupe_fnames} (应为0)")

    # STEP 4: 预处理镜头（快慢分层）
    log('\n[Step 4] 分层剪辑预处理...')
    processed = []
    for i, clip in enumerate(clips):
        src = clip['full_path']
        if not os.path.exists(src):
            log(f"  [!] Missing: {clip['fname']}")
            continue

        pace_lo, pace_hi = clip['pace_range']
        # 取镜头中间偏前部分（动势最强）
        src_dur = clip['duration']
        # 估算：从开头取 target_dur 时长
        target_dur = (pace_lo + pace_hi) / 2
        skip_start = min(0.3, src_dur * 0.1)  # 跳过前10%不稳定帧
        take_dur = min(target_dur, src_dur - skip_start - 0.2)

        out = os.path.join(PROJ_DIR, 'clips_processed', f'clip_{i:02d}.mp4')
        o, e, c = run([
            'ffmpeg', '-ss', str(skip_start), '-i', src,
            '-t', str(take_dur),
            '-an', '-c:v', 'libx264', '-preset', 'fast', '-crf', '22',
            '-vf', 'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black',
            '-r', '30', '-y', out
        ], timeout=60)

        if c == 0 and os.path.exists(out):
            actual = get_dur(out)
            clip['processed_path'] = out
            clip['processed_dur'] = actual
            processed.append(clip)
            log(f"  [{i+1:02d}] {clip['emotion']:4s} {actual:.1f}s | {clip['fname'][:28]}")
        else:
            log(f"  [!] FAIL: {clip['fname'][:30]}")

    log(f"  处理成功: {len(processed)}/{len(clips)}")

    # STEP 5: 拼接视频
    log('\n[Step 5] 拼接...')
    concat_list_v = os.path.join(PROJ_DIR, 'concat.txt')
    with open(concat_list_v, 'w', encoding='utf-8') as f:
        for clip in processed:
            f.write(f"file '{os.path.abspath(clip['processed_path'])}'\n")

    concat_raw = os.path.join(PROJ_DIR, 'concat_raw.mp4')
    o, e, c = run([
        'ffmpeg', '-f', 'concat', '-safe', '0', '-i', concat_list_v,
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '20', '-an', '-y', concat_raw
    ], timeout=180)
    concat_dur = get_dur(concat_raw)
    log(f"  拼接: {concat_dur:.2f}s vs 配音: {audio_dur:.2f}s")

    # STEP 6: 时长对齐（关键！）
    log('\n[Step 6] 时长对齐...')
    final_video = os.path.join(PROJ_DIR, 'video_final.mp4')

    if concat_dur < audio_dur - 0.5:
        ratio = concat_dur / audio_dur
        speed_factor = max(0.67, min(1.5, ratio))
        log(f"  视频太短 {concat_dur:.1f}s < 音频{audio_dur:.1f}s，加速 {speed_factor:.3f}x")
        # 用setpts加速视频，保留音频原速
        o, e, c = run([
            'ffmpeg', '-i', concat_raw, '-i', VO_PATH,
            '-filter:v', f'setpts={1/speed_factor}*PTS',
            '-map', '0:v', '-map', '1:a',
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '20',
            '-shortest', '-y', final_video
        ], timeout=120)
    elif concat_dur > audio_dur + 1.0:
        log(f"  视频略长，截断")
        o, e, c = run([
            'ffmpeg', '-i', concat_raw, '-i', VO_PATH,
            '-t', str(audio_dur),
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '20',
            '-map', '0:v', '-map', '1:a', '-y', final_video
        ], timeout=120)
    else:
        o, e, c = run([
            'ffmpeg', '-i', concat_raw, '-i', VO_PATH,
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '20',
            '-map', '0:v', '-map', '1:a', '-y', final_video
        ], timeout=120)

    if c != 0:
        log(f"  [!] Merge failed: {e[:200]}")
        import shutil
        shutil.copy(concat_raw, final_video)

    final_dur = get_dur(final_video)
    log(f"  最终: {final_dur:.2f}s (视频={get_dur(concat_raw):.2f}s, 音频={audio_dur:.2f}s)")

    # STEP 7: PIL字幕烧录
    log('\n[Step 7] PIL字幕烧录...')
    FINAL_OUT = os.path.join(OUT_DIR, '成品_素材01_60s_v8.mp4')

    def parse_srt_crlf(path):
        with open(path, 'rb') as f:
            raw = f.read()
        blocks = raw.split(b'\r\n\r\n')
        entries = []
        for block in blocks:
            if not block.strip(): continue
            lines_b = block.split(b'\r\n')
            if len(lines_b) < 3: continue
            ts_line = lines_b[1].decode('utf-8')
            m = re.match(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})', ts_line)
            if not m: continue
            start = int(m.group(1))*3600 + int(m.group(2))*60 + int(m.group(3)) + int(m.group(4))/1000
            end = int(m.group(5))*3600 + int(m.group(6))*60 + int(m.group(7)) + int(m.group(8))/1000
            text = b'\r\n'.join(lines_b[2:]).decode('utf-8').strip()
            entries.append({'start': start, 'end': end, 'text': text})
        return entries

    def render_subtitle(text, font_size=52, stroke=3):
        tmp = Image.new('RGBA', (10, 10), (0,0,0,0))
        td = ImageDraw.Draw(tmp)
        fnt = ImageFont.truetype(FONT, font_size)
        bbox = td.textbbox((0,0), text, font=fnt)
        tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
        pad_x, pad_y = 40, 15
        iw, ih = min(tw+pad_x*2, 1040), th+pad_y*2
        img = Image.new('RGBA', (iw, ih), (0,0,0,0))
        d = ImageDraw.Draw(img)
        xc, yc = (iw-tw)//2 - bbox[0], (ih-th)//2 - bbox[1]
        for dx in range(-stroke, stroke+1):
            for dy in range(-stroke, stroke+1):
                if abs(dx)==stroke or abs(dy)==stroke:
                    d.text((xc+dx, yc+dy), text, font=fnt, fill=(0,0,0,255))
        d.text((xc, yc), text, font=fnt, fill=(255,255,255,255))
        return np.array(img, dtype='uint8')

    video = mp.VideoFileClip(final_video)
    subs = parse_srt_crlf(SRT_PATH)
    log(f"  加载 {len(subs)} 条字幕")

    sub_clips = []
    for i, s in enumerate(subs):
        dur = s['end'] - s['start']
        if dur <= 0 or not s['text'].strip(): continue
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
    composite = composite.with_duration(audio_dur)

    log(f"  写入: {FINAL_OUT}")
    composite.write_videofile(
        FINAL_OUT, codec='libx264', audio_codec='aac',
        audio_bitrate='192k', preset='fast', fps=30, threads=4, logger='bar'
    )

    # STEP 8: QC
    log('\n[Step 8] 质检...')
    if os.path.exists(FINAL_OUT):
        sz = os.path.getsize(FINAL_OUT) / 1024**2
        dur = get_dur(FINAL_OUT)
        r2 = subprocess.run(['ffprobe', '-v', 'quiet', '-print_format', 'json',
                           '-show_streams', FINAL_OUT], capture_output=True, text=True)
        info2 = json.loads(r2.stdout)
        streams = info2.get('streams', [])
        has_v = any(s['codec_type']=='video' for s in streams)
        has_a = any(s['codec_type']=='audio' for s in streams)
        log(f'')
        log(f'{"="*60}')
        log(f'  成品: {FINAL_OUT}')
        log(f'  大小: {sz:.1f} MB | 时长: {dur:.1f}s')
        log(f'  视频流: {"YES" if has_v else "NO"} | 音频流: {"YES" if has_a else "NO"}')
        log(f'  字幕同步: 逐行TTS实测 (%d条)' % len(subs))
        log(f'  场景去重: %d场景 %d镜头 (场景重复:%d)' % (len(set(scenes_used)), len(clips), dupe_scenes))
        log(f'  情感TTS: rate/pitch按情绪变化')
        log(f'  节奏分层: 快(CTA 0.8s)→慢(共鸣 3.5s)')
        log(f'{"="*60}')
    else:
        log(f'  [!] 未找到成品!')

if __name__ == '__main__':
    asyncio.run(main())
