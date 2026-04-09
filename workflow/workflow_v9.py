#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import subprocess, json, os, asyncio, re, time, shutil
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import moviepy as mp

BASE_DIR  = r"C:\Users\Administrator\Desktop\素材01\西梅奇亚籽轻上饮品"
OUT_DIR   = r"C:\Users\Administrator\Desktop"
FRAME_DIR = os.path.join(BASE_DIR, "_frames")
PROJ_DIR  = os.path.join(FRAME_DIR, "project_60s_v9")
for d in [PROJ_DIR, os.path.join(PROJ_DIR, "clips_processed")]:
    os.makedirs(d, exist_ok=True)

FONT = r"C:\Windows\Fonts\msyh.ttc"

LINES = [
    ("夜深了躺在床上刷手机，肚子咕咕叫想吃夜宵，",         "共鸣",   "+15%", "-8Hz"),
    ("外卖划了半天又怕胖，关掉又不甘心。",                  "纠结",   "+15%", "-8Hz"),
    ("直到闺蜜给我安利了这瓶——",                          "转折",   "+25%", "-5Hz"),
    ("轻上西梅奇亚籽饮品，",                               "介绍",   "+25%", "-5Hz"),
    ("配料表一扫，零脂肪，配料干净，",                       "验证",   "+25%", "-5Hz"),
    ("关键是里面真的有16颗智利西梅，奇亚籽也是实实在在看得见的那种。", "成分", "+25%", "-5Hz"),
    ("倒出来就能喝，酸酸甜甜的，像在嚼一杯液体水果。",      "口感",   "+25%", "-5Hz"),
    ("关键是零添加蔗糖，喝完嘴巴里是清爽的那种甜，",        "特点",   "+25%", "-5Hz"),
    ("我现在办公桌常备，下午茶时段来一瓶，",                 "场景",   "+25%", "-5Hz"),
    ("那些天天吃外卖重油重辣的，还有久坐少动管不住嘴的，",  "人群",   "+25%", "-5Hz"),
    ("想保持身材又不想亏嘴的，真心可以试试。",              "邀请",   "+20%", "-3Hz"),
    ("现在直播间搞活动，算下来一瓶才三块多，",               "价格",   "+38%", "+5Hz"),
    ("我上次回购了五箱，家里人抢着喝，",                    "见证",   "+20%", "-3Hz"),
    ("电商平台十万+销量，口碑一直很稳，",                    "背书",   "+25%", "-5Hz"),
    ("朋友推荐给我的，现在我也推荐给你。",                   "社交",   "+25%", "-5Hz"),
    ("智利西梅配进口奇亚籽，每一瓶都是高膳食纤维，",        "成分",   "+25%", "-5Hz"),
    ("零脂肪配方，好喝轻体无负担，",                         "总结",   "+25%", "-5Hz"),
    ("这波活动库存有限，卖完就恢复原价了，",                 "紧迫",   "+45%", "+8Hz"),
    ("想尝鲜的朋友，赶紧下单，",                              "催促",   "+45%", "+8Hz"),
    ("和家人一起享用，一起保持轻盈好状态！",                  "CTA",    "+18%", "-3Hz"),
]

PACE_MAP = {
    "共鸣": (2.5, 3.5), "纠结": (2.0, 2.5), "转折": (1.8, 2.5),
    "介绍": (1.5, 2.0), "验证": (1.8, 2.2), "成分": (2.0, 3.0),
    "口感": (2.0, 2.5), "特点": (2.0, 2.5), "场景": (2.0, 2.5),
    "人群": (2.5, 3.0), "邀请": (1.8, 2.2), "价格": (1.2, 1.8),
    "见证": (1.5, 2.0), "背书": (1.5, 2.0), "社交": (1.5, 2.0),
    "总结": (1.5, 2.0), "紧迫": (0.8, 1.2), "催促": (0.8, 1.2),
    "CTA":  (1.8, 2.5),
}

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

MATCH_TYPES = [
    ["人群场景", "RAW素材"],
    ["人群场景", "RAW素材"],
    ["产品展示", "产品场景A"],
    ["产品展示", "产品场景A"],
    ["产品展示", "产品场景A"],
    ["产品展示", "产品场景A"],
    ["产品展示", "产品场景A"],
    ["产品展示", "产品场景A"],
    ["室内", "产品场景B"],
    ["人群场景", "RAW素材"],
    ["人群场景", "产品场景A"],
    ["产品场景B", "RAW素材"],
    ["人群场景", "RAW素材"],
    ["RAW素材", "产品场景B"],
    ["人群场景", "达人场景"],
    ["产品展示", "产品场景A"],
    ["产品展示", "产品场景A"],
    ["产品场景B", "RAW素材"],
    ["产品场景B", "室内"],
    ["人群场景", "室内"],
]

def mlog(msg):
    print("[%s] %s" % (time.strftime("%H:%M:%S"), msg), flush=True)

def run_cmd(cmd, timeout=120):
    r = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", timeout=timeout)
    return r.stdout, r.stderr, r.returncode

def get_dur(fp):
    try:
        o, _, c = run_cmd(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", fp])
        if c == 0 and o.strip():
            return float(o.strip())
    except:
        pass
    return 0

def load_clip_db():
    csv_path = os.path.join(BASE_DIR, "西梅奇亚籽轻上饮品_产品镜头索引.csv")
    clips = {}
    if os.path.exists(csv_path):
        import csv as csvmod
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csvmod.reader(f)
            header = next(reader)
            for row in reader:
                if len(row) < 6:
                    continue
                try:
                    fname = row[1].strip()
                    ctype = row[3].strip()
                    dur = float(row[5].strip())
                    clips[fname] = {
                        "fname": fname,
                        "type": ctype,
                        "duration": dur,
                        "full_path": os.path.join(BASE_DIR, fname),
                    }
                except:
                    pass
    return clips

def get_scene(fname):
    parts = fname.replace(".MOV", "").replace(".MP4", "").split("_")
    # Use HH_MM only (minute-level) to allow 2 clips per shooting minute
    if len(parts) >= 5:
        return "_".join(parts[:4])  # YYYY_MM_DD_HH
    return fname[:16]

def select_clips_v9(clip_db, lines):
    buckets = {}
    for fname, info in clip_db.items():
        if not os.path.exists(info["full_path"]):
            continue
        ct = info["type"]
        if ct not in buckets:
            buckets[ct] = []
        buckets[ct].append((fname, info))

    used_fnames = set()
    used_scenes = set()
    selected = []

    for i, (text, emotion, rate, pitch) in enumerate(lines):
        preferred = MATCH_TYPES[i] if i < len(MATCH_TYPES) else ["RAW素材"]
        fname_found = None
        info_found = None

        for pt in preferred:
            for fname, info in buckets.get(pt, []):
                if fname in used_fnames:
                    continue
                scene = get_scene(fname)
                if scene in used_scenes:
                    continue
                fname_found = fname
                info_found = info
                used_fnames.add(fname)
                used_scenes.add(scene)
                break
            if fname_found:
                break

        if fname_found is None:
            # Try all buckets for any available clip
            for fname, info in clip_db.items():
                if fname in used_fnames:
                    continue
                used_fnames.add(fname)
                used_scenes.add(get_scene(fname))
                fname_found = fname
                info_found = info
                break

        if fname_found:
            pace_lo, pace_hi = PACE_MAP.get(emotion, (1.5, 2.5))
            selected.append({
                "line_idx": i, "text": text, "emotion": emotion,
                "rate": rate, "pitch": pitch,
                "fname": fname_found, "full_path": info_found["full_path"],
                "duration": info_found["duration"], "type": info_found["type"],
                "scene": get_scene(fname_found),
                "pace_lo": pace_lo, "pace_hi": pace_hi,
                "goal": SHOT_GOALS[i],
            })
            mlog("  [%02d] %s | %s" % (i+1, emotion, fname_found[:30]))
        else:
            mlog("  [%02d] %s | [NO CLIP]" % (i+1, emotion))

    return selected

async def gen_tts(text, path, rate="+25%", pitch="-5Hz"):
    import edge_tts
    await edge_tts.Communicate(text, voice="zh-CN-XiaoxiaoNeural",
                                rate=rate, pitch=pitch).save(path)

def fmt_ts(t):
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = int((t - int(t)) * 1000)
    return "%02d:%02d:%02d,%03d" % (h, m, s, ms)

async def main():
    mlog("=" * 60)
    mlog("V9: Fixed clip selection + audio merge")
    mlog("=" * 60)

    mlog("[Step 1] TTS per line...")
    TMP_DIR = os.path.join(PROJ_DIR, "_tmp")
    os.makedirs(TMP_DIR, exist_ok=True)

    timings = []
    cur = 0.0
    for i, (text, emotion, rate, pitch) in enumerate(LINES):
        p = os.path.join(TMP_DIR, "line_%02d.mp3" % i)
        await gen_tts(text, p, rate=rate, pitch=pitch)
        dur = get_dur(p)
        timings.append({
            "line": i+1, "text": text, "emotion": emotion,
            "rate": rate, "pitch": pitch,
            "start": round(cur, 3), "end": round(cur + dur, 3), "dur": round(dur, 3)
        })
        mlog("  %02d | %.2f->%.2f (%.2fs) | %s | %s %s" % (i+1, cur, cur+dur, dur, emotion, rate, pitch))
        cur += dur + 0.05

    total_audio = cur - 0.05
    mlog("  Total audio: %.2fs" % total_audio)

    mlog("[Step 2] Merge audio...")
    concat_list = os.path.join(TMP_DIR, "audio_concat.txt")
    with open(concat_list, "w", encoding="utf-8") as f:
        for i in range(len(LINES)):
            p = os.path.join(TMP_DIR, "line_%02d.mp3" % i)
            if os.path.exists(p):
                f.write("file '" + os.path.abspath(p) + "'\n")

    VO_PATH = os.path.join(OUT_DIR, "voiceover_v9.mp3")
    o, e, c = run_cmd([
        "ffmpeg", "-f", "concat", "-safe", "0", "-i", concat_list,
        "-acodec", "libmp3lame", "-ab", "192k", "-y", VO_PATH
    ], timeout=90)

    if c != 0 or not os.path.exists(VO_PATH):
        mlog("  [WARN] Audio merge failed, copying first line")
        shutil.copy(os.path.join(TMP_DIR, "line_00.mp3"), VO_PATH)

    audio_dur = get_dur(VO_PATH)
    mlog("  Merged audio: %.2fs" % audio_dur)

    SRT_PATH = os.path.join(OUT_DIR, "subs_v9.srt")
    with open(SRT_PATH, "wb") as f:
        for t in timings:
            f.write(("%d\r\n%s --> %s\r\n%s\r\n\r\n" % (t["line"], fmt_ts(t["start"]), fmt_ts(t["end"]), t["text"])).encode("utf-8"))
    mlog("  SRT: %d entries" % len(timings))

    mlog("[Step 3] Load clip DB...")
    clip_db = load_clip_db()
    mlog("  DB: %d clips" % len(clip_db))

    mlog("[Step 4] V9 greedy clip selection...")
    clips = select_clips_v9(clip_db, LINES)
    mlog("  Selected: %d clips" % len(clips))

    scenes_used = [c["scene"] for c in clips]
    fnames_used = [c["fname"] for c in clips]
    dupe_scenes = len(scenes_used) - len(set(scenes_used))
    dupe_fnames = len(fnames_used) - len(set(fnames_used))
    mlog("  Scene dupes: %d | Fname dupes: %d" % (dupe_scenes, dupe_fnames))

    mlog("[Step 5] Preprocess clips...")
    processed = []
    for i, clip in enumerate(clips):
        src = clip["full_path"]
        if not os.path.exists(src):
            mlog("  [!] Missing: " + clip["fname"])
            continue

        src_dur = clip["duration"]
        pace_lo, pace_hi = clip["pace_lo"], clip["pace_hi"]
        target = (pace_lo + pace_hi) / 2.0
        skip_start = min(0.5, src_dur * 0.15)
        take_dur = min(target, max(0.8, src_dur - skip_start - 0.3))

        out = os.path.join(PROJ_DIR, "clips_processed", "clip_%02d.mp4" % i)
        o, e, c = run_cmd([
            "ffmpeg", "-ss", str(skip_start), "-i", src,
            "-t", str(take_dur),
            "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black",
            "-r", "30", "-y", out
        ], timeout=60)

        if c == 0 and os.path.exists(out):
            actual_dur = get_dur(out)
            clip["processed_path"] = out
            clip["processed_dur"] = actual_dur
            processed.append(clip)
            mlog("  [%02d] %s %.1fs | %s" % (i+1, clip["emotion"], actual_dur, clip["fname"][:28]))
        else:
            mlog("  [!] FAIL: " + clip["fname"][:30])

    mlog("  Processed: %d/%d" % (len(processed), len(clips)))

    mlog("[Step 6] Concat video...")
    concat_list_v = os.path.join(PROJ_DIR, "concat.txt")
    with open(concat_list_v, "w", encoding="utf-8") as f:
        for clip in processed:
            f.write("file '" + os.path.abspath(clip["processed_path"]) + "'\n")

    concat_raw = os.path.join(PROJ_DIR, "concat_raw.mp4")
    o, e, c = run_cmd([
        "ffmpeg", "-f", "concat", "-safe", "0", "-i", concat_list_v,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-an", "-y", concat_raw
    ], timeout=180)
    concat_dur = get_dur(concat_raw)
    mlog("  Concat: %.2fs | Audio: %.2fs" % (concat_dur, audio_dur))

    mlog("[Step 7] Duration alignment...")
    final_video = os.path.join(PROJ_DIR, "video_final.mp4")

    if concat_dur < audio_dur - 0.3:
        ratio = concat_dur / audio_dur
        spd = max(0.70, min(1.5, ratio))
        mlog("  Short: %.1fs < %.1fs, speed up %.3fx" % (concat_dur, audio_dur, spd))
        o, e, c = run_cmd([
            "ffmpeg", "-i", concat_raw, "-i", VO_PATH,
            "-filter:v", "setpts=" + str(1/spd) + "*PTS",
            "-map", "0:v", "-map", "1:a",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-shortest", "-y", final_video
        ], timeout=120)
        if c != 0:
            mlog("  setpts failed, truncate fallback")
            o, e, c = run_cmd([
                "ffmpeg", "-i", concat_raw, "-i", VO_PATH,
                "-t", str(audio_dur),
                "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                "-map", "0:v", "-map", "1:a", "-y", final_video
            ], timeout=120)
    elif concat_dur > audio_dur + 0.5:
        mlog("  Long: %.1fs > %.1fs, truncate" % (concat_dur, audio_dur))
        o, e, c = run_cmd([
            "ffmpeg", "-i", concat_raw, "-i", VO_PATH,
            "-t", str(audio_dur),
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-map", "0:v", "-map", "1:a", "-y", final_video
        ], timeout=120)
    else:
        o, e, c = run_cmd([
            "ffmpeg", "-i", concat_raw, "-i", VO_PATH,
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-map", "0:v", "-map", "1:a", "-y", final_video
        ], timeout=120)

    if c != 0 or not os.path.exists(final_video):
        mlog("  [!] Merge failed, copying concat_raw")
        shutil.copy(concat_raw, final_video)

    final_dur = get_dur(final_video)
    mlog("  After merge: %.2fs" % final_dur)

    mlog("[Step 8] PIL subtitle burn...")
    FINAL_OUT = os.path.join(OUT_DIR, "成品_素材01_60s_v9.mp4")

    def parse_srt_crlf(path):
        with open(path, "rb") as f:
            raw = f.read()
        blocks = raw.split(b"\r\n\r\n")
        entries = []
        for block in blocks:
            if not block.strip():
                continue
            lines_b = block.split(b"\r\n")
            if len(lines_b) < 3:
                continue
            ts_line = lines_b[1].decode("utf-8")
            m = re.match(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})", ts_line)
            if not m:
                continue
            start = int(m.group(1))*3600 + int(m.group(2))*60 + int(m.group(3)) + int(m.group(4))/1000
            end = int(m.group(5))*3600 + int(m.group(6))*60 + int(m.group(7)) + int(m.group(8))/1000
            text = b"\r\n".join(lines_b[2:]).decode("utf-8").strip()
            entries.append({"start": start, "end": end, "text": text})
        return entries

    def render_subtitle(text, font_size=52, stroke=3):
        tmp = Image.new("RGBA", (10, 10), (0,0,0,0))
        td = ImageDraw.Draw(tmp)
        fnt = ImageFont.truetype(FONT, font_size)
        bbox = td.textbbox((0,0), text, font=fnt)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        pad_x, pad_y = 40, 15
        iw = min(tw + pad_x * 2, 1040)
        ih = th + pad_y * 2
        img = Image.new("RGBA", (iw, ih), (0,0,0,0))
        d = ImageDraw.Draw(img)
        xc = (iw - tw) // 2 - bbox[0]
        yc = (ih - th) // 2 - bbox[1]
        for dx in range(-stroke, stroke + 1):
            for dy in range(-stroke, stroke + 1):
                if abs(dx) == stroke or abs(dy) == stroke:
                    d.text((xc+dx, yc+dy), text, font=fnt, fill=(0,0,0,255))
        d.text((xc, yc), text, font=fnt, fill=(255,255,255,255))
        return np.array(img, dtype="uint8")

    video = mp.VideoFileClip(final_video)
    subs = parse_srt_crlf(SRT_PATH)
    mlog("  Subtitle entries: %d" % len(subs))

    sub_clips = []
    for s in subs:
        dur = s["end"] - s["start"]
        if dur <= 0 or not s["text"].strip():
            continue
        try:
            sub_img = render_subtitle(s["text"])
            tc = mp.ImageClip(sub_img).with_duration(dur)
            x_pos = (1080 - sub_img.shape[1]) / 2
            y_pos = video.h - sub_img.shape[0] - 80
            tc = tc.with_position((x_pos, y_pos)).with_start(s["start"])
            sub_clips.append(tc)
        except Exception as ex:
            mlog("  [!] Sub error: " + str(ex))

    composite = mp.CompositeVideoClip([video] + sub_clips, size=(1080, 1920))
    composite = composite.with_duration(audio_dur)

    mlog("  Writing: " + FINAL_OUT)
    composite.write_videofile(
        FINAL_OUT, codec="libx264", audio_codec="aac",
        audio_bitrate="192k", preset="fast", fps=30, threads=4, logger="bar"
    )

    mlog("[Step 9] QC...")
    if os.path.exists(FINAL_OUT):
        sz = os.path.getsize(FINAL_OUT) / 1024**2
        dur = get_dur(FINAL_OUT)
        r2 = subprocess.run(["ffprobe", "-v", "quiet", "-print_format", "json",
                           "-show_streams", FINAL_OUT], capture_output=True, text=True)
        info2 = json.loads(r2.stdout)
        streams = info2.get("streams", [])
        has_v = any(s["codec_type"] == "video" for s in streams)
        has_a = any(s["codec_type"] == "audio" for s in streams)
        mlog("")
        mlog("=" * 60)
        mlog("  OUTPUT: " + FINAL_OUT)
        mlog("  SIZE: %.1f MB | DURATION: %.1fs" % (sz, dur))
        mlog("  VIDEO: %s | AUDIO: %s" % ("YES" if has_v else "NO", "YES" if has_a else "NO"))
        mlog("  SUBS: %d entries" % len(subs))
        mlog("  CLIPS: %d (scene dupes: %d)" % (len(clips), dupe_scenes))
        mlog("=" * 60)
    else:
        mlog("  [!] Output not found!")

if __name__ == "__main__":
    asyncio.run(main())
