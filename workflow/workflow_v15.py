#!/usr/bin/env python3
"""V17: 45秒版 - MiniMax TTS配音（更真实的真人感）
核心升级：用MiniMax TTS替代edge_tts，解决配音机械感问题
- Voice: Chinese_Female_1 (MiniMax)
- 素材：全局去重80个镜头
- 前摇帧：亮度检测自动入画时刻
"""
import subprocess, os, asyncio, time, csv as csvmod, random, requests
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import moviepy as mp

BASE_DIR  = r"D:\VideoProjects\material"
OUT_DIR   = r"C:\Users\Administrator\Desktop"
FRAME_DIR = r"C:\Users\Administrator\.openclaw\workspace\_frames"
PROJ_DIR  = os.path.join(FRAME_DIR, "project_60s_v17")
for d in [PROJ_DIR, os.path.join(PROJ_DIR, "clips_processed")]:
    os.makedirs(d, exist_ok=True)

FONT = r"C:\Windows\Fonts\msyh.ttc"
MINIMAX_API_KEY = 'sk-cp-43u5mhw5Iazv62TqWcCJaSb2LN0YzkHDUTJ3J-_tP9uPgbqd4UPDar6L1jQEORSjcYEk0PbUZWuF8GotaLMO4CxnRx5MQfazCx6ln7Gku45t08vv32TBEC4'
MINIMAX_URL = 'https://api.minimax.io/v1/t2a_v2'

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
# MiniMax TTS（同步版本）
# ─────────────────────────────────────────
def minimax_tts(text, voice_id="Chinese_Female_1", speed=1.0):
    """调用MiniMax TTS API，返回MP3二进制数据"""
    headers = {
        'Authorization': 'Bearer ' + MINIMAX_API_KEY,
        'Content-Type': 'application/json'
    }
    data = {
        'model': 'speech-2.8-hd',
        'text': text,
        'stream': False,
        'output_format': 'hex',
        'voice_setting': {'voice_id': voice_id, 'speed': speed},
        'audio_setting': {'sample_rate': 32000, 'bitrate': 128000, 'format': 'mp3'}
    }
    r = requests.post(MINIMAX_URL, headers=headers, json=data, timeout=30)
    if r.status_code != 200:
        raise Exception("HTTP " + str(r.status_code) + ": " + r.text[:200])
    resp = r.json()
    br = resp.get('base_resp', {})
    code = br.get('status_code', 0)
    if code != 0:
        raise Exception("MiniMax API error " + str(code) + ": " + br.get('status_msg', ''))
    audio_hex = resp.get('data', {}).get('audio', '')
    if not audio_hex:
        raise Exception("No audio in response")
    return bytes.fromhex(audio_hex)


# ─────────────────────────────────────────
# 逐句TTS + 测实际时长
# ─────────────────────────────────────────
def generate_tts(voice_id="Chinese_Female_1", speed=1.0):
    """生成16句TTS，测实际时长"""
    dur_map = {}
    for i, (text, _) in enumerate(LINES):
        path = os.path.join(PROJ_DIR, "tts_%03d.mp3" % i)
        try:
            audio_bytes = minimax_tts(text, voice_id=voice_id, speed=speed)
            with open(path, 'wb') as f:
                f.write(audio_bytes)
            dur = get_dur(path)
            dur_map[i] = max(dur, 0.3)
            mlog("  [tts] [%02d] %s... -> %.2fs" % (i+1, text[:12], dur_map[i]))
        except Exception as e:
            mlog("  [tts] [%02d] ERR: %s" % (i+1, e))
            dur_map[i] = 2.5
    return dur_map


# ─────────────────────────────────────────
# 自动检测产品入画时刻
# ─────────────────────────────────────────
def find_entry_time(MOV_path, max_check=4.0):
    """通过帧亮度分析，检测产品稳定入画时刻"""
    import tempfile

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
            cx, cy = iw // 2, ih // 2
            crop = np.array(img.crop((cx - 300, cy - 400, cx + 300, cy + 400)), dtype=float)
            brightness.append((t, crop.mean()))
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    if len(brightness) < 3:
        return 0.3

    early = [b for t, b in brightness if t <= 1.5]
    late = [b for t, b in brightness if t > 1.5]

    if not early or not late:
        return 0.5

    avg_early = sum(early) / len(early)
    avg_late = sum(late) / len(late)

    if avg_late - avg_early > 8:
        target = avg_early + (avg_late - avg_early) * 0.7
        for t, b in brightness:
            if b >= target:
                mlog("  [entry] t=%.1fs brightness=%d" % (t, b))
                return max(0.3, t - 0.2)
        return 1.5

    return 0.5


# ─────────────────────────────────────────
# 镜头选择（全局去重）
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
                clips.append({
                    "fname": fname, "type": ctype, "duration": dur,
                    "full_path": full, "scene": scene
                })
            except: pass
    return clips


def select_clips_global_dedup(clips, needed=80):
    """全局去重：每个fname只出现一次"""
    clips_shuffled = clips[:]
    random.seed(42)
    random.shuffle(clips_shuffled)

    by_scene = {}
    for c in clips:
        sc = c["scene"]
        if sc not in by_scene:
            by_scene[sc] = []
        by_scene[sc].append(c)

    scenes = sorted(by_scene.keys())
    selected = []
    used_fnames = set()
    last_scene = None

    for round_num in range(10):
        if len(selected) >= needed:
            break

        candidates_pool = []
        for sc in scenes:
            for c in by_scene[sc]:
                if c["fname"] not in used_fnames and os.path.exists(c["full_path"]):
                    candidates_pool.append(c)

        if not candidates_pool:
            break

        def sort_key(c):
            return (1 if c["scene"] == last_scene else 0, len(selected) % 5)

        candidates_pool.sort(key=sort_key)

        for c in candidates_pool:
            if c["fname"] in used_fnames:
                continue
            consecutive_same = 0
            if selected and selected[-1]["scene"] == c["scene"]:
                consecutive_same = 1
                if len(selected) >= 2 and selected[-2]["scene"] == c["scene"]:
                    consecutive_same = 2
            if consecutive_same >= 2:
                continue

            selected.append(c)
            used_fnames.add(c["fname"])
            last_scene = c["scene"]
            if len(selected) >= needed:
                break

    mlog("  [dedup] %d unique clips from %d total" % (len(selected), len(clips)))
    return selected[:needed]


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
def main():
    mlog("=" * 60)
    mlog("V17: MiniMax TTS配音（更真实）")
    mlog("  Voice: Chinese_Female_1 (MiniMax)")
    mlog("  镜头：全局去重80个")
    mlog("  前摇帧：亮度检测自动入画时刻")
    mlog("=" * 60)

    # Step 1: TTS (MiniMax Chinese_Female_1)
    mlog("\n[Step 1] TTS (MiniMax Chinese_Female_1)...")
    dur_map = generate_tts(voice_id="Chinese_Female_1", speed=1.0)
    total_dur = sum(dur_map.values())
    mlog("  Total audio: %.1fs" % total_dur)

    # Step 2: 字幕
    mlog("\n[Step 2] 字幕...")
    subs = []
    t = 0.0
    for i, (text, _) in enumerate(LINES):
        end = t + dur_map[i]
        subs.append({"n": i+1, "text": text, "start": t, "end": end})
        t = end

    SRT = os.path.join(PROJ_DIR, "subs_v17.srt")
    with open(SRT, "wb") as f:
        for s in subs:
            block = ("%d\r\n%s --> %s\r\n%s\r\n\r\n" % (
                s["n"], fmt_ts(s["start"]), fmt_ts(s["end"]), s["text"]
            )).encode("utf-8")
            f.write(block)
    mlog("  SRT: %d entries, total %.1fs" % (len(subs), subs[-1]["end"]))

    # Step 3: 选镜头
    mlog("\n[Step 3] 选镜头（全局去重）...")
    clips = load_clip_db()
    mlog("  DB: %d clips" % len(clips))
    selected = select_clips_global_dedup(clips, needed=80)
    mlog("  Selected: %d clips" % len(selected))

    # Step 4: 处理镜头
    mlog("\n[Step 4] 处理镜头...")
    processed = []
    for i, c in enumerate(selected):
        src = c["full_path"]
        if not os.path.exists(src):
            mlog("  [!] Missing: %s" % c["fname"]); continue

        entry_t = find_entry_time(src, max_check=4.0)
        src_dur = c["duration"]
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
            mlog("  [%02d] %s entry=%.1fs take=%.2fs | %s" % (i, c["fname"][:22], entry_t, actual, c["scene"][:16]))

    total_clip_dur = sum(p["dur"] for p in processed)
    mlog("  Total clips: %.1fs | Need: %.1fs" % (total_clip_dur, total_dur))

    # Step 5: 拼接
    mlog("\n[Step 5] 拼接...")

    def build_concat_shuffled(target_dur, clips_list):
        result = []
        t = 0.0
        start_idx = random.randint(0, len(clips_list) - 1)
        order = clips_list[start_idx:] + clips_list[:start_idx]
        idx = 0
        while t < target_dur:
            c = order[idx % len(order)]
            result.append(c)
            t += c["dur"]
            idx += 1
        return result

    concat_y = build_concat_shuffled(total_dur, processed)
    concat_a = build_concat_shuffled(total_dur, processed)

    concat_y_txt = os.path.join(PROJ_DIR, "concat_y.txt")
    concat_a_txt = os.path.join(PROJ_DIR, "concat_a.txt")

    for txt_path, clip_list in [(concat_y_txt, concat_y), (concat_a_txt, concat_a)]:
        with open(txt_path, "w", encoding="utf-8") as f:
            for c in clip_list:
                f.write("file '" + os.path.abspath(c["path"]) + "'\n")

    # Step 6: 合并+字幕
    mlog("\n[Step 6] 合并音视频+字幕...")

    def make_final(concat_txt, suffix):
        concat_raw = os.path.join(PROJ_DIR, "concat_raw_%s.mp4" % suffix)
        run_cmd(["ffmpeg", "-f", "concat", "-safe", "0", "-i", concat_txt,
                 "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-an", "-y", concat_raw],
                timeout=180)
        concat_dur = get_dur(concat_raw)

        # Merge audio segments
        merged_audio = os.path.join(PROJ_DIR, "merged_audio_%s.mp3" % suffix)
        audio_list_txt = os.path.join(PROJ_DIR, "audio_parts_%s.txt" % suffix)
        with open(audio_list_txt, "w", encoding="utf-8") as f:
            for i in range(len(LINES)):
                part = os.path.join(PROJ_DIR, "tts_%03d.mp3" % i)
                if os.path.exists(part):
                    f.write("file '" + os.path.abspath(part) + "'\n")
        run_cmd(["ffmpeg", "-f", "concat", "-safe", "0", "-i", audio_list_txt,
                 "-c", "copy", "-y", merged_audio], timeout=60)
        audio_dur = get_dur(merged_audio)

        # Pad video to audio length
        pad_dur = max(0, audio_dur - concat_dur + 0.5)
        pad_out = os.path.join(PROJ_DIR, "pad_%s.mp4" % suffix)
        pad_txt = os.path.join(PROJ_DIR, "concat_pad_%s.txt" % suffix)
        with open(pad_txt, "w", encoding="utf-8") as f:
            f.write("file '" + os.path.abspath(concat_raw) + "'\n")
            if pad_dur > 0.1:
                run_cmd(["ffmpeg", "-f", "lavfi", "-i",
                         "color=c=black:s=1080x1920:d=%.1f:r=30" % pad_dur,
                         "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-y", pad_out],
                        timeout=30)
                f.write("file '" + os.path.abspath(pad_out) + "'\n")
        video_padded = os.path.join(PROJ_DIR, "concat_padded_%s.mp4" % suffix)
        run_cmd(["ffmpeg", "-f", "concat", "-safe", "0", "-i", pad_txt,
                 "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-an", "-y", video_padded],
                timeout=60)

        # Merge with audio
        final_no_sub = os.path.join(PROJ_DIR, "final_%s_nosub.mp4" % suffix)
        run_cmd(["ffmpeg", "-i", video_padded, "-i", merged_audio,
                 "-map", "0:v", "-map", "1:a", "-t", str(audio_dur),
                 "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-y", final_no_sub],
                timeout=120)

        # Burn subtitles
        mlog("  Sub burn (%s)..." % suffix)
        final_out = os.path.join(OUT_DIR, "成品_素材01_45s_v17_%s.mp4" % suffix)
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
                mlog("  [!] Sub error: %s" % ex)
        composite = mp.CompositeVideoClip(
            [video] + sub_clips, size=(1080, 1920)
        ).with_duration(audio_dur)
        composite.write_videofile(
            final_out, codec="libx264", audio_codec="aac",
            audio_bitrate="192k", preset="fast", fps=30, threads=4, logger="bar"
        )
        sz = os.path.getsize(final_out) / 1024**2
        mlog("  FINALE: %s (%.1fMB)" % (os.path.basename(final_out), sz))

    make_final(concat_y_txt, "y")
    make_final(concat_a_txt, "a")

    mlog("\nDone!")
    mlog("  成品_素材01_45s_v17_y.mp4")
    mlog("  成品_素材01_45s_v17_a.mp4")

if __name__ == "__main__":
    main()
