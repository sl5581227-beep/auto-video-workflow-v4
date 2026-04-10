#!/usr/bin/env python3
"""V15: 45秒版 - 三大核心修复
1. 前摇帧：自动检测产品稳定入画时刻（亮度曲线分析）
2. 配音：XiaoxiaoNeural +1%，测试style参数降机械感
3. 镜头重复：强制不同场景严格交替
"""
import subprocess, os, asyncio, time, csv as csvmod
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import moviepy as mp

BASE_DIR  = r"D:\VideoProjects\material"
OUT_DIR   = r"C:\Users\Administrator\Desktop"
FRAME_DIR = r"C:\Users\Administrator\.openclaw\workspace\_frames"
PROJ_DIR  = os.path.join(FRAME_DIR, "project_60s_v15")
for d in [PROJ_DIR, os.path.join(PROJ_DIR, "clips_processed")]:
    os.makedirs(d, exist_ok=True)

FONT = r"C:\Windows\Fonts\msyh.ttc"

LINES = [
    ("深夜刷手机肚子饿，外卖怕胖不吃又馋，",     3.8),
    ("闺蜜给我安利了这瓶轻上西梅奇亚籽，",       2.8),
    ("配料表干净，零脂肪，配料就三行，",          3.2),
    ("16颗智利西梅+进口奇亚籽，",                2.2),
    ("倒出来就能喝，酸酸甜甜的，",                2.2),
    ("零添加蔗糖，喝完嘴里是清爽的甜，",           2.8),
    ("我现在办公桌常备，下午茶来一瓶，",           2.8),
    ("重油外卖的同事也爱上了，",                  2.2),
    ("一瓶才三块多，直播间活动价，",               2.8),
    ("我上次回购了五箱，家里人抢着喝，",           3.0),
    ("电商平台十万+销量，口碑一直很稳，",          2.8),
    ("朋友推荐给我的，现在我也推荐给你。",         3.2),
    ("每天一瓶，高膳食纤维，零脂肪，",             2.8),
    ("好喝轻体无负担，保持轻盈好状态，",          2.8),
    ("库存有限，卖完恢复原价，",                   2.5),
    ("想保持身材又不想亏嘴的，赶紧下单，",         3.2),
]
FULL_SCRIPT = "".join([l[0] for l in LINES])

def mlog(msg):
    print("[" + time.strftime("%H:%M:%S") + "] " + msg, flush=True)

def run_cmd(cmd, timeout=120):
    r = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", timeout=timeout)
    return r.stdout, r.stderr, r.returncode

def get_dur(fp):
    try:
        o, _, c = run_cmd(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", fp])
        if c == 0 and o.strip():
            return float(o.strip())
    except: pass
    return 0

def fmt_ts(t):
    h = int(t // 3600); m = int((t % 3600) // 60)
    s = int(t % 60); ms = int((t - int(t)) * 1000)
    return "%02d:%02d:%02d,%03d" % (h, m, s, ms)

# ─────────────────────────────────────────
# 配音研究：edge_tts参数测试
# ─────────────────────────────────────────
async def probe_voices():
    """测试edge_tts的style/controllable参数，找降机械感方案"""
    import edge_tts
    test_text = "朋友们好，今天给大家推荐一款好喝又健康的饮品。"
    test_dir = os.path.join(PROJ_DIR, "voice_probe")
    os.makedirs(test_dir, exist_ok=True)

    configs = [
        # (voice, rate, pitch, name) - style param not supported
        ("zh-CN-XiaoxiaoNeural", "+1%", None, "xiaoxiao_+1%"),
        ("zh-CN-YunxiNeural",    "+0%", None, "yunxi_normal"),
        ("zh-CN-YunxiNeural",    "+0%", "-3Hz", "yunxi_normal_-3Hz"),
        ("zh-CN-YunxiNeural",    "+5%", None, "yunxi_+5%"),
        ("zh-CN-XiaoxiaoNeural", "+0%", None, "xiaoxiao_normal"),
    ]

    for voice, rate, pitch, name in configs:
        path = os.path.join(test_dir, f"{name}.mp3")
        try:
            comm = edge_tts.Communicate(test_text, voice=voice, rate=rate,
                                     pitch=pitch if pitch else None)
            await comm.save(path)
            sz = os.path.getsize(path)
            mlog(f"  [probe] {name}: {sz//1024}KB")
        except Exception as e:
            mlog(f"  [probe] {name}: ERR {e}")

# ─────────────────────────────────────────
# 核心1: 自动检测产品稳定入画时刻
# ─────────────────────────────────────────
def find_entry_time(MOV_path, max_check=4.0):
    """
    通过帧分析检测产品"稳定就位"的时刻。
    策略：提取前max_check秒内多个时间点的帧，
    计算中心区域亮度。当亮度开始稳定（变化<阈值）时，
    认为产品已入画。
    
    返回: skip_seconds (float) - 需要跳过的秒数
    """
    import tempfile, shutil

    times = [round(t * 0.5, 2) for t in range(1, int(max_check * 2) + 1)]
    brightness = []

    for t in times:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            r = subprocess.run([
                "ffmpeg", "-ss", str(t), "-i", MOV_path,
                "-vframes", "1", "-q:v", "2", "-y", tmp_path
            ], capture_output=True, timeout=10)
            if r.returncode != 0 or not os.path.exists(tmp_path):
                continue
            img = Image.open(tmp_path).convert("RGB")
            iw, ih = img.size
            # 中心区域
            cx, cy = iw // 2, ih // 2
            crop = np.array(img.crop((cx - 300, cy - 400, cx + 300, cy + 400)), dtype=float)
            brightness.append((t, crop.mean()))
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    if len(brightness) < 3:
        return 0.3  # 默认跳过0.3s

    # 找亮度"稳定"的拐点
    # 策略：前3个点的亮度趋势如果是上升（入画），跳过到第3个点之后
    early = [b for t, b in brightness if t <= 1.5]
    late = [b for t, b in brightness if t > 1.5]

    if not early or not late:
        return 0.5

    avg_early = sum(early) / len(early)
    avg_late = sum(late) / len(late)

    # 如果后期比早期明显更亮 = 产品从暗到亮逐渐入画
    if avg_late - avg_early > 8:
        # 找到第一个亮度接近最终稳定的时刻
        target = avg_early + (avg_late - avg_early) * 0.7
        for t, b in brightness:
            if b >= target:
                mlog(f"  [entry] detected entry at t={t:.1f}s (brightness={b:.0f})")
                return max(0.3, t - 0.2)
        return 1.5

    # 否则亮度已稳定，默认跳过一小段
    return 0.5

# ─────────────────────────────────────────
# 核心2: 逐句TTS测实际时长
# ─────────────────────────────────────────
async def get_actual_durations(voice="zh-CN-XiaoxiaoNeural", rate="+1%"):
    """每句单独TTS生成，测实际音频时长"""
    import edge_tts
    dur_map = {}
    for i, (text, _) in enumerate(LINES):
        path = os.path.join(PROJ_DIR, f"tts_{i:03d}.mp3")
        try:
            comm = edge_tts.Communicate(text, voice=voice, rate=rate)
            await comm.save(path)
            dur = get_dur(path)
            dur_map[i] = max(dur, 0.3)
            mlog(f"  [tts] [{i+1:02d}] {text[:12]}... -> {dur:.2f}s")
        except Exception as e:
            mlog(f"  [tts] [{i+1:02d}] ERR: {e}")
            dur_map[i] = 2.5
    return dur_map

# ─────────────────────────────────────────
# 核心3: 镜头选择（场景严格交替）
# ─────────────────────────────────────────
def load_clip_db():
    csv_path = os.path.join(BASE_DIR, "西梅奇亚籽轻上饮品_产品镜头索引.csv")
    clips = []
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csvmod.reader(f)
        next(reader)
        for row in reader:
            if len(row) < 6: continue
            try:
                fname = row[1].strip()
                ctype = row[3].strip()
                dur = float(row[5].strip())
                full = os.path.join(BASE_DIR, fname)
                p = fname.replace(".MOV","").replace(".MP4","").split("_")
                scene = "_".join(p[:4]) if len(p)>=4 else fname[:16]
                hour = p[3] if len(p)>=4 else "00"
                clips.append({
                    "fname": fname, "type": ctype, "duration": dur,
                    "full_path": full, "scene": scene, "hour": hour
                })
            except: pass
    return clips

def select_clips_no_adjacent_repeat(clips, needed=48):
    """
    修复场景重复：不允许相邻2个镜头属于同一scene。
    轮询不同scene，同scene不连续出现。
    """
    # 按scene分组
    by_scene = {}
    for c in clips:
        sc = c["scene"]
        if sc not in by_scene:
            by_scene[sc] = []
        by_scene[sc].append(c)

    scenes = sorted(by_scene.keys())
    selected = []
    used_fnames = set()
    # 记录上一个使用的scene（避免连续）
    last_scene = None
    scene_iter = 0

    while len(selected) < needed:
        # 轮询找下一个不同scene
        for _ in range(len(scenes)):
            sc = scenes[scene_iter % len(scenes)]
            scene_iter += 1
            if sc == last_scene:
                continue
            # 从这个scene里找一个未使用的clip
            candidates = [
                c for c in by_scene[sc]
                if c["fname"] not in used_fnames and os.path.exists(c["full_path"])
            ]
            if candidates:
                c = candidates[0]
                selected.append(c)
                used_fnames.add(c["fname"])
                last_scene = sc
                break
        else:
            # 所有scene都用完了，清空重新来过（允许复用fname）
            used_fnames.clear()
            last_scene = None

    return selected

# ─────────────────────────────────────────
# 字幕渲染
# ─────────────────────────────────────────
def render_subtitle(text, font_size=52, stroke=3):
    tmp = Image.new("RGBA",(10,10),(0,0,0,0)); td = ImageDraw.Draw(tmp)
    fnt = ImageFont.truetype(FONT, font_size)
    bbox = td.textbbox((0,0),text,font=fnt)
    tw=bbox[2]-bbox[0]; th=bbox[3]-bbox[1]
    pad_x,pad_y=40,15; iw=min(tw+pad_x*2,1040); ih=th+pad_y*2
    img=Image.new("RGBA",(iw,ih),(0,0,0,0)); d=ImageDraw.Draw(img)
    xc=(iw-tw)//2-bbox[0]; yc=(ih-th)//2-bbox[1]
    for dx in range(-stroke,stroke+1):
        for dy in range(-stroke,stroke+1):
            if abs(dx)==stroke or abs(dy)==stroke:
                d.text((xc+dx,yc+dy),text,font=fnt,fill=(0,0,0,255))
    d.text((xc,yc),text,font=fnt,fill=(255,255,255,255))
    return np.array(img,dtype="uint8")

# ─────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────
async def main():
    mlog("=" * 60)
    mlog("V15: 三大核心修复")
    mlog("  1. 前摇帧：自动检测产品入画时刻")
    mlog("  2. 配音：XiaoxiaoNeural +1%")
    mlog("  3. 镜头重复：场景严格交替")
    mlog("=" * 60)

    # Step 0: Voice probe
    mlog("\n[Step 0] 配音参数测试...")
    await probe_voices()

    # Step 1: TTS
    mlog("\n[Step 1] TTS (XiaoxiaoNeural +1%)...")
    dur_map = await get_actual_durations("zh-CN-XiaoxiaoNeural", "+1%")
    total_dur = sum(dur_map.values())
    mlog(f"  Total audio: {total_dur:.1f}s")

    # Step 2: 字幕（基于实际时长）
    mlog("\n[Step 2] 字幕...")
    subs = []
    t = 0.0
    for i, (text, _) in enumerate(LINES):
        end = t + dur_map[i]
        subs.append({"n": i+1, "text": text, "start": t, "end": end})
        t = end

    SRT = os.path.join(PROJ_DIR, "subs_v15.srt")
    with open(SRT, "wb") as f:
        for s in subs:
            block = ("%d\r\n%s --> %s\r\n%s\r\n\r\n" % (
                s["n"], fmt_ts(s["start"]), fmt_ts(s["end"]), s["text"]
            )).encode("utf-8")
            f.write(block)
    mlog(f"  SRT: {len(subs)} entries, total {subs[-1]['end']:.1f}s")

    # Step 3: 选镜头（场景严格交替）
    mlog("\n[Step 3] 选镜头（场景严格交替）...")
    clips = load_clip_db()
    mlog(f"  DB: {len(clips)} clips")
    selected = select_clips_no_adjacent_repeat(clips, needed=60)
    mlog(f"  Selected: {len(selected)} clips")

    # 验证无相邻重复
    errors = 0
    for i in range(len(selected) - 1):
        if selected[i]["scene"] == selected[i+1]["scene"]:
            mlog(f"  [!] scene repeat at {i},{i+1}: {selected[i]['scene']}")
            errors += 1
    if errors == 0:
        mlog("  PASS: no adjacent scene repeats")
    else:
        mlog(f"  WARN: {errors} adjacent scene repeats found")

    # Step 4: 处理镜头（自动检测入画时刻）
    mlog("\n[Step 4] 处理镜头（自动检测入画时刻）...")
    processed = []
    for i, c in enumerate(selected):
        src = c["full_path"]
        if not os.path.exists(src):
            mlog(f"  [!] Missing: {c['fname']}"); continue

        # 自动检测入画时刻
        entry_t = find_entry_time(src, max_check=4.0)
        src_dur = c["duration"]
        # 取entry之后的内容，但也要留结尾余量
        take = min(2.0, max(0.8, src_dur - entry_t - 0.5))
        skip_start = entry_t

        out = os.path.join(PROJ_DIR, "clips_processed", "c_%03d.mp4" % i)
        o, e, cc = run_cmd([
            "ffmpeg", "-ss", str(skip_start), "-i", src, "-t", str(take), "-an",
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black",
            "-r", "30", "-y", out
        ], timeout=60)

        if cc == 0 and os.path.exists(out):
            actual = get_dur(out)
            processed.append({"path": out, "dur": actual, "fname": c["fname"], "scene": c["scene"]})
            mlog(f"  [{i:02d}] {c['fname'][:22]} entry={entry_t:.1f}s take={actual:.1f}s | {c['scene'][:16]}")

    total_clip_dur = sum(p["dur"] for p in processed)
    mlog(f"  Total clips: {total_clip_dur:.1f}s | Need: {total_dur:.1f}s")

    # Step 5: 拼接（循环填充）
    mlog("\n[Step 5] 拼接...")
    def build_concat(target_dur, clips_list):
        result = []
        t = 0.0
        ci = 0
        while t < target_dur:
            c = clips_list[ci % len(clips_list)]
            result.append(c)
            t += c["dur"]
            ci += 1
        return result

    concat_y = build_concat(total_dur, processed)
    concat_a = build_concat(total_dur, processed)

    concat_y_txt = os.path.join(PROJ_DIR, "concat_y.txt")
    concat_a_txt = os.path.join(PROJ_DIR, "concat_a.txt")

    for txt_path, clip_list in [(concat_y_txt, concat_y), (concat_a_txt, concat_a)]:
        with open(txt_path, "w", encoding="utf-8") as f:
            for c in clip_list:
                f.write("file '" + os.path.abspath(c["path"]) + "'\n")

    # Step 6: 合并+字幕
    mlog("\n[Step 6] 合并音视频+字幕...")

    async def make_final(concat_txt, suffix):
        # Concat video
        concat_raw = os.path.join(PROJ_DIR, f"concat_raw_{suffix}.mp4")
        run_cmd(["ffmpeg", "-f", "concat", "-safe", "0", "-i", concat_txt,
                 "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-an", "-y", concat_raw],
                timeout=180)
        concat_dur = get_dur(concat_raw)

        # Merge audio segments
        merged_audio = os.path.join(PROJ_DIR, f"merged_audio_{suffix}.mp3")
        audio_list_txt = os.path.join(PROJ_DIR, f"audio_parts_{suffix}.txt")
        with open(audio_list_txt, "w", encoding="utf-8") as f:
            for i in range(len(LINES)):
                part = os.path.join(PROJ_DIR, f"tts_{i:03d}.mp3")
                if os.path.exists(part):
                    f.write("file '" + os.path.abspath(part) + "'\n")
        run_cmd(["ffmpeg", "-f", "concat", "-safe", "0", "-i", audio_list_txt,
                 "-c", "copy", "-y", merged_audio], timeout=60)
        audio_dur = get_dur(merged_audio)

        # Pad video to audio length
        pad_dur = max(0, audio_dur - concat_dur + 0.5)
        pad_out = os.path.join(PROJ_DIR, f"pad_{suffix}.mp4")
        pad_txt = os.path.join(PROJ_DIR, f"concat_pad_{suffix}.txt")
        with open(pad_txt, "w", encoding="utf-8") as f:
            f.write("file '" + os.path.abspath(concat_raw) + "'\n")
            if pad_dur > 0.1:
                run_cmd(["ffmpeg", "-f", "lavfi", "-i",
                         f"color=c=black:s=1080x1920:d={pad_dur:.1f}:r=30",
                         "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-y", pad_out],
                        timeout=30)
                f.write("file '" + os.path.abspath(pad_out) + "'\n")
        video_padded = os.path.join(PROJ_DIR, f"concat_padded_{suffix}.mp4")
        run_cmd(["ffmpeg", "-f", "concat", "-safe", "0", "-i", pad_txt,
                 "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-an", "-y", video_padded],
                timeout=60)

        # Merge with audio
        final_no_sub = os.path.join(PROJ_DIR, f"final_{suffix}_nosub.mp4")
        run_cmd(["ffmpeg", "-i", video_padded, "-i", merged_audio,
                 "-map", "0:v", "-map", "1:a", "-t", str(audio_dur),
                 "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-y", final_no_sub],
                timeout=120)

        # Burn subtitles
        mlog(f"  字幕烧录({suffix})...")
        final_out = os.path.join(OUT_DIR, f"成品_素材01_45s_v15_{suffix}.mp4")
        video = mp.VideoFileClip(final_no_sub)
        sub_clips = []
        for s in subs:
            dur = s["end"] - s["start"]
            if dur <= 0.05 or not s["text"].strip():
                continue
            try:
                sub_img = render_subtitle(s["text"])
                tc = mp.ImageClip(sub_img).with_duration(dur)
                tc = tc.with_position(
                    ((1080 - sub_img.shape[1]) // 2, video.h - sub_img.shape[0] - 80)
                ).with_start(s["start"])
                sub_clips.append(tc)
            except Exception as ex:
                mlog(f"  [!] Sub error: {ex}")
        composite = mp.CompositeVideoClip(
            [video] + sub_clips, size=(1080, 1920)
        ).with_duration(audio_dur)
        composite.write_videofile(
            final_out, codec="libx264", audio_codec="aac",
            audio_bitrate="192k", preset="fast", fps=30, threads=4, logger="bar"
        )
        sz = os.path.getsize(final_out) / 1024**2
        mlog(f"  FINALE: {os.path.basename(final_out)} ({sz:.1f}MB)")

    await make_final(concat_y_txt, "yunxi")
    await make_final(concat_a_txt, "aixia")

    mlog("\n完成！")
    mlog("  成品_素材01_45s_v15_yunxi.mp4")
    mlog("  成品_素材01_45s_v15_aixia.mp4")

if __name__ == "__main__":
    asyncio.run(main())