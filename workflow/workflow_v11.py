#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V13: 45秒版 - 修复Aixia尾帧freeze
关键修复：每个音频独立生成padding文件，concat_raw不跨调用重用
"""
import subprocess, json, os, asyncio, re, time, shutil, tempfile
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import moviepy as mp

BASE_DIR  = r"D:\VideoProjects\material"
OUT_DIR   = r"C:\Users\Administrator\Desktop"
FRAME_DIR = r"C:\Users\Administrator\.openclaw\workspace\_frames"
PROJ_DIR  = os.path.join(FRAME_DIR, "project_60s_v13")
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
TOTAL_DUR = sum(l[1] for l in LINES)

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

async def gen_tts(text, path, voice, rate="+20%", pitch=None):
    import edge_tts
    if pitch:
        comm = edge_tts.Communicate(text, voice=voice, rate=rate, pitch=pitch)
    else:
        comm = edge_tts.Communicate(text, voice=voice, rate=rate)
    await comm.save(path)

def load_clip_db():
    csv_path = os.path.join(BASE_DIR, "西梅奇亚籽轻上饮品_产品镜头索引.csv")
    import csv as csvmod
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
                clips.append({"fname":fname,"type":ctype,"duration":dur,
                              "full_path":full,"scene":scene,"hour":hour})
            except: pass
    return clips

def select_diverse(clips):
    by_hour = {}
    for c in clips:
        h = c["hour"]
        if h not in by_hour: by_hour[h] = []
        by_hour[h].append(c)
    hours = sorted(by_hour.keys())
    selected = []; used = set()
    for i in range(len(LINES)):
        h = hours[i % len(hours)]
        candidates = [c for c in by_hour.get(h,[]) if c["fname"] not in used and os.path.exists(c["full_path"])]
        if candidates:
            c = candidates[0]; used.add(c["fname"])
            selected.append({"idx":i,"clip":c,"target_dur":LINES[i][1]})
        else:
            for c in clips:
                if c["fname"] not in used and os.path.exists(c["full_path"]):
                    used.add(c["fname"])
                    selected.append({"idx":i,"clip":c,"target_dur":LINES[i][1]}); break
    return selected

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

async def main():
    mlog("="*60)
    mlog("V13: 45秒版 - Aixia尾帧freeze修复")
    mlog("="*60)
    
    # TTS
    mlog("\n[Step 1] TTS...")
    V13_YUNXI = os.path.join(PROJ_DIR, "v13_yunxi.mp3")
    V13_AIXIA = os.path.join(PROJ_DIR, "v13_aixia.mp3")
    
    mlog("  Yunxi...")
    await gen_tts(FULL_SCRIPT, V13_YUNXI, "zh-CN-YunxiNeural", "+20%", "-5Hz")
    dur_yunxi = get_dur(V13_YUNXI)
    mlog("  Yunxi: %.2fs" % dur_yunxi)
    
    mlog("  Aixia...")
    await gen_tts(FULL_SCRIPT, V13_AIXIA, "zh-CN-XiaoxiaoNeural", "+15%")
    dur_aixia = get_dur(V13_AIXIA)
    mlog("  Aixia: %.2fs" % dur_aixia)
    
    # SRT
    mlog("\n[Step 2] 字幕...")
    SRT = os.path.join(PROJ_DIR, "subs_v13.srt")
    ratio_y = dur_yunxi / TOTAL_DUR
    subs = []
    t = 0.0
    for i,(text,dur) in enumerate(LINES):
        end = t + dur * ratio_y
        subs.append({"n":i+1,"text":text,"start":t,"end":end})
        t = end
    with open(SRT,"wb") as f:
        for s in subs:
            block = ("%d\r\n%s --> %s\r\n%s\r\n\r\n" % (
                s["n"],fmt_ts(s["start"]),fmt_ts(s["end"]),s["text"])).encode("utf-8")
            f.write(block)
    mlog("  SRT: %d entries | total: %.1fs" % (len(subs), subs[-1]["end"]))
    
    # Clips
    mlog("\n[Step 3] 加载镜头库...")
    clips = load_clip_db()
    mlog("  DB: %d clips" % len(clips))
    selected = select_diverse(clips)
    mlog("  Selected: %d clips" % len(selected))
    
    mlog("\n[Step 4] 处理镜头...")
    processed = []
    for item in selected:
        c = item["clip"]
        src = c["full_path"]
        if not os.path.exists(src):
            mlog("  [!] Missing: " + c["fname"]); continue
        src_dur = c["duration"]; target = item["target_dur"]
        skip_start = min(0.2, src_dur*0.05)
        take = min(target, max(0.6, src_dur-skip_start-0.1))
        out = os.path.join(PROJ_DIR, "clips_processed", "c_%03d.mp4" % len(processed))
        o,e,c2 = run_cmd([
            "ffmpeg","-ss",str(skip_start),"-i",src,"-t",str(take),"-an",
            "-c:v","libx264","-preset","fast","-crf","22",
            "-vf","scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black",
            "-r","30","-y",out],timeout=60)
        if c2==0 and os.path.exists(out):
            actual = get_dur(out)
            processed.append({"path":out,"dur":actual,"fname":c["fname"]})
            mlog("  %s %.1fs->%.1fs" % (c["fname"][:22], actual, take))
    
    total_clip_dur = sum(p["dur"] for p in processed)
    mlog("  Total clips: %.1fs | Yunxi:%.1fs Aixia:%.1fs" % (total_clip_dur, dur_yunxi, dur_aixia))
    
    # Concat
    mlog("\n[Step 5] 拼接...")
    concat_txt = os.path.join(PROJ_DIR, "concat.txt")
    with open(concat_txt,"w",encoding="utf-8") as f:
        for p in processed:
            f.write("file '"+os.path.abspath(p["path"])+"'\n")
    concat_raw = os.path.join(PROJ_DIR, "concat_raw.mp4")
    run_cmd(["ffmpeg","-f","concat","-safe","0","-i",concat_txt,
             "-c:v","libx264","-preset","fast","-crf","20","-an","-y",concat_raw],timeout=180)
    concat_dur = get_dur(concat_raw)
    mlog("  Concat: %.2fs" % concat_dur)
    
    # Merge per audio (fresh pad per call)
    mlog("\n[Step 6] 合并音视频+字幕...")
    
    def make_video(audio_path, audio_dur, suffix):
        pad_dur = max(0, audio_dur - concat_dur + 0.5)
        pad_out = os.path.join(PROJ_DIR, "pad_%s.mp4" % suffix)
        pad_txt = os.path.join(PROJ_DIR, "concat_pad_%s.txt" % suffix)
        with open(pad_txt,"w",encoding="utf-8") as f:
            f.write("file '"+os.path.abspath(concat_raw)+"'\n")
            if pad_dur > 0.1:
                run_cmd(["ffmpeg","-f","lavfi","-i","color=c=black:s=1080x1920:d=%.1f:r=30"%pad_dur,
                         "-c:v","libx264","-preset","fast","-crf","23","-y",pad_out],timeout=30)
                f.write("file '"+os.path.abspath(pad_out)+"'\n")
        video_padded = os.path.join(PROJ_DIR, "concat_padded_%s.mp4" % suffix)
        run_cmd(["ffmpeg","-f","concat","-safe","0","-i",pad_txt,
                 "-c:v","libx264","-preset","fast","-crf","20","-an","-y",video_padded],timeout=60)
        mlog("  %s: video=%.2fs audio=%.2fs pad=%.1fs" % (suffix, get_dur(video_padded), audio_dur, pad_dur))
        
        final_no_sub = os.path.join(PROJ_DIR, "final_%s_nosub.mp4" % suffix)
        run_cmd(["ffmpeg","-i",video_padded,"-i",audio_path,
                 "-map","0:v","-map","1:a","-t",str(audio_dur),
                 "-c:v","libx264","-preset","fast","-crf","20","-y",final_no_sub],timeout=120)
        
        mlog("  字幕烧录(%s)..." % suffix)
        final_out = os.path.join(OUT_DIR, "成品_素材01_45s_%s.mp4" % suffix)
        video = mp.VideoFileClip(final_no_sub)
        sub_clips = []
        for s in subs:
            dur = s["end"]-s["start"]
            if dur<=0.05 or not s["text"].strip(): continue
            try:
                sub_img = render_subtitle(s["text"])
                tc = mp.ImageClip(sub_img).with_duration(dur)
                tc = tc.with_position(((1080-sub_img.shape[1])//2, video.h-sub_img.shape[0]-80)).with_start(s["start"])
                sub_clips.append(tc)
            except Exception as ex:
                mlog("  [!] Sub: "+str(ex))
        composite = mp.CompositeVideoClip([video]+sub_clips, size=(1080,1920)).with_duration(audio_dur)
        composite.write_videofile(final_out, codec="libx264", audio_codec="aac",
            audio_bitrate="192k", preset="fast", fps=30, threads=4, logger="bar")
        sz = os.path.getsize(final_out)/1024**2
        mlog("  FINALE: %s (%.1fMB)" % (os.path.basename(final_out), sz))
    
    make_video(V13_YUNXI, dur_yunxi, "yunxi")
    make_video(V13_AIXIA, dur_aixia, "aixia")
    mlog("\n完成！桌面：")
    mlog("  成品_素材01_45s_yunxi.mp4")
    mlog("  成品_素材01_45s_aixia.mp4")

if __name__ == "__main__":
    asyncio.run(main())
