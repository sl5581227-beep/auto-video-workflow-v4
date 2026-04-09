#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V14: 45秒版 - 三大修复
1. 前摇帧：每个clip多切0.5s开头，去掉无用的前摇帧
2. 镜头重复：同场景不连续 + 从更多场景采样
3. 字幕同步：每句单独TTS测实际时长，精准分配字幕时间点
"""
import subprocess, os, asyncio, time, shutil
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import moviepy as mp

BASE_DIR  = r"D:\VideoProjects\material"
OUT_DIR   = r"C:\Users\Administrator\Desktop"
FRAME_DIR = r"C:\Users\Administrator\.openclaw\workspace\_frames"
PROJ_DIR  = os.path.join(FRAME_DIR, "project_60s_v14")
for d in [PROJ_DIR, os.path.join(PROJ_DIR, "clips_processed")]:
    os.makedirs(d, exist_ok=True)

FONT = r"C:\Windows\Fonts\msyh.ttc"

# 45秒版 - 16句精简文案
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

async def gen_tts(text, path, voice, rate="+20%", pitch=None):
    import edge_tts
    if pitch:
        comm = edge_tts.Communicate(text, voice=voice, rate=rate, pitch=pitch)
    else:
        comm = edge_tts.Communicate(text, voice=voice, rate=rate)
    await comm.save(path)

async def get_actual_durations():
    """每句单独TTS，测实际时长（解决字幕同步问题）"""
    import edge_tts
    dur_yunxi = {}
    dur_aixia = {}
    for i, (text, _) in enumerate(LINES):
        # Yunxi
        p_y = os.path.join(PROJ_DIR, "tts_y_%03d.mp3" % i)
        await gen_tts(text, p_y, "zh-CN-YunxiNeural", "+20%", "-5Hz")
        dur_yunxi[i] = max(get_dur(p_y), 0.5)
        # Aixia
        p_a = os.path.join(PROJ_DIR, "tts_a_%03d.mp3" % i)
        await gen_tts(text, p_a, "zh-CN-XiaoxiaoNeural", "+15%")
        dur_aixia[i] = max(get_dur(p_a), 0.5)
    return dur_yunxi, dur_aixia

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

def select_diverse_no_repeat(clips, needed=48):
    """
    修复1：同场景不能连续出现，跨场景采样
    修复2：选更多镜头（48个），尽量覆盖不同场景
    """
    by_scene = {}
    for c in clips:
        sc = c["scene"]
        if sc not in by_scene: by_scene[sc] = []
        by_scene[sc].append(c)
    scenes = sorted(by_scene.keys())
    
    # 轮询场景，每场景取1个，确保不连续
    selected = []
    used_scenes = set()
    scene_idx = 0
    attempts = 0
    
    while len(selected) < needed and attempts < needed * 3:
        attempts += 1
        sc = scenes[scene_idx % len(scenes)]
        scene_idx += 1
        
        # 从未选过或离上次出现足够远的scene里选
        candidates = [c for c in by_scene[sc]
                      if os.path.exists(c["full_path"])
                      and c not in selected]
        if candidates:
            c = candidates[0]
            selected.append(c)
    
    # 如果还不够，从所有剩余clips里补
    used = set(c["fname"] for c in selected)
    for c in clips:
        if c["fname"] not in used and os.path.exists(c["full_path"]) and len(selected) < needed:
            selected.append(c)
            used.add(c["fname"])
    
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
    mlog("V14: 三大修复 - 前摇帧/镜头重复/字幕同步")
    mlog("="*60)
    
    # STEP 1: 每句单独TTS测实际时长
    mlog("\n[Step 1] 每句TTS测实际时长...")
    dur_yunxi, dur_aixia = await get_actual_durations()
    
    total_y = sum(dur_yunxi.values())
    total_a = sum(dur_aixia.values())
    mlog("  Yunxi总: %.1fs | Aixia总: %.1fs" % (total_y, total_a))
    for i,(text,_) in enumerate(LINES):
        mlog("  [%02d] %.1fs | %s" % (i+1, dur_yunxi[i], text[:12]))
    
    # STEP 2: 建立字幕（用实际Yunxi时长）
    mlog("\n[Step 2] 字幕（精准时间）...")
    subs = []
    t = 0.0
    for i,(text,_) in enumerate(LINES):
        end = t + dur_yunxi[i]
        subs.append({"n":i+1,"text":text,"start":t,"end":end})
        t = end
    
    SRT = os.path.join(PROJ_DIR, "subs_v14.srt")
    with open(SRT,"wb") as f:
        for s in subs:
            block = ("%d\r\n%s --> %s\r\n%s\r\n\r\n" % (
                s["n"],fmt_ts(s["start"]),fmt_ts(s["end"]),s["text"])).encode("utf-8")
            f.write(block)
    mlog("  SRT: %d entries | total: %.1fs" % (len(subs), subs[-1]["end"]))
    
    # STEP 3: 选更多镜头（48个）
    mlog("\n[Step 3] 选48个镜头（场景去重）...")
    clips = load_clip_db()
    selected = select_diverse_no_repeat(clips, needed=48)
    
    # 统计场景覆盖
    scene_counts = {}
    for c in selected:
        sc = c["scene"]
        scene_counts[sc] = scene_counts.get(sc, 0) + 1
    mlog("  Selected: %d clips | %d unique scenes" % (len(selected), len(scene_counts)))
    mlog("  Scenes: %s" % str({k:v for k,v in list(scene_counts.items())[:8]}))
    for c in selected[:16]:
        mlog("  %s | %s" % (c["fname"][:24], c["scene"][:20]))
    
    # STEP 4: 处理镜头（修复前摇帧：多切0.5s开头）
    mlog("\n[Step 4] 处理镜头（切0.5s前摇）...")
    processed = []
    for i, c in enumerate(selected):
        src = c["full_path"]
        if not os.path.exists(src):
            mlog("  [!] Missing: " + c["fname"]); continue
        src_dur = c["duration"]
        # 修复：前摇帧 - 跳过前0.5s（前摇帧）
        PREROLL = 0.5
        skip_start = PREROLL
        take = min(2.0, max(0.8, src_dur - PREROLL - 0.1))
        out = os.path.join(PROJ_DIR, "clips_processed", "c_%03d.mp4" % i)
        o,e,c2 = run_cmd([
            "ffmpeg","-ss",str(skip_start),"-i",src,"-t",str(take),"-an",
            "-c:v","libx264","-preset","fast","-crf","22",
            "-vf","scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black",
            "-r","30","-y",out],timeout=60)
        if c2==0 and os.path.exists(out):
            actual = get_dur(out)
            processed.append({"path":out,"dur":actual,"fname":c["fname"],"scene":c["scene"]})
            mlog("  [%02d] %s %.1fs | %s" % (i, c["fname"][:20], actual, c["scene"][:16]))
    
    total_clip_dur = sum(p["dur"] for p in processed)
    mlog("  Total clips: %.1fs | Yunxi:%.1fs Aixia:%.1fs" % (
        total_clip_dur, total_y, total_a))
    
    # STEP 5: 拼接（repeat clips to fill audio）
    mlog("\n[Step 5] 拼接...")
    concat_txt = os.path.join(PROJ_DIR, "concat.txt")
    
    # 按目标时长分配镜头，不够就循环
    def build_concat_list(target_dur, clips_list):
        result = []
        t = 0.0
        ci = 0
        while t < target_dur:
            c = clips_list[ci % len(clips_list)]
            result.append(c)
            t += c["dur"]
            ci += 1
        return result
    
    concat_for_yunxi = build_concat_list(total_y, processed)
    concat_for_aixia = build_concat_list(total_a, processed)
    
    concat_dur_y = sum(c["dur"] for c in concat_for_yunxi)
    concat_dur_a = sum(c["dur"] for c in concat_for_aixia)
    mlog("  Yunxi concat: %.1fs (%d clips, looped)" % (concat_dur_y, len(concat_for_yunxi)))
    mlog("  Aixia concat: %.1fs (%d clips, looped)" % (concat_dur_a, len(concat_for_aixia)))
    
    def write_concat(path, clips_list):
        with open(path,"w",encoding="utf-8") as f:
            for c in clips_list:
                f.write("file '"+os.path.abspath(c["path"])+"'\n")
    
    concat_y_txt = os.path.join(PROJ_DIR, "concat_y.txt")
    concat_a_txt = os.path.join(PROJ_DIR, "concat_a.txt")
    write_concat(concat_y_txt, concat_for_yunxi)
    write_concat(concat_a_txt, concat_for_aixia)
    
    # STEP 6: 合并+字幕
    mlog("\n[Step 6] 合并音视频+字幕...")
    
    async def make_final(audio_durs, concat_txt_file, suffix):
        import edge_tts
        
        # Merge audio segments
        merged_audio = os.path.join(PROJ_DIR, "merged_%s.mp3" % suffix)
        tmp_list = os.path.join(PROJ_DIR, "audio_parts_%s.txt" % suffix)
        with open(tmp_list,"w",encoding="utf-8") as f:
            for i in range(len(LINES)):
                part = os.path.join(PROJ_DIR, ("tts_y_%03d.mp3" if suffix=="yunxi" else "tts_a_%03d.mp3") % i)
                if os.path.exists(part):
                    f.write("file '"+os.path.abspath(part)+"'\n")
        run_cmd(["ffmpeg","-f","concat","-safe","0","-i",tmp_list,
                 "-c","copy","-y",merged_audio],timeout=60)
        actual_audio_dur = get_dur(merged_audio)
        
        # Concat video
        concat_raw = os.path.join(PROJ_DIR, "concat_raw_%s.mp4" % suffix)
        run_cmd(["ffmpeg","-f","concat","-safe","0","-i",concat_txt_file,
                 "-c:v","libx264","-preset","fast","-crf","20","-an","-y",concat_raw],timeout=180)
        concat_dur = get_dur(concat_raw)
        
        # Pad to audio length
        pad_dur = max(0, actual_audio_dur - concat_dur + 0.5)
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
        mlog("  %s: video=%.2fs audio=%.2fs pad=%.1fs" % (
            suffix, get_dur(video_padded), actual_audio_dur, pad_dur))
        
        # Merge with audio
        final_no_sub = os.path.join(PROJ_DIR, "final_%s_nosub.mp4" % suffix)
        run_cmd(["ffmpeg","-i",video_padded,"-i",merged_audio,
                 "-map","0:v","-map","1:a","-t",str(actual_audio_dur),
                 "-c:v","libx264","-preset","fast","-crf","20","-y",final_no_sub],timeout=120)
        
        # Subtitle burn
        mlog("  字幕烧录(%s)..." % suffix)
        final_out = os.path.join(OUT_DIR, "成品_素材01_45s_v14_%s.mp4" % suffix)
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
        composite = mp.CompositeVideoClip([video]+sub_clips, size=(1080,1920)).with_duration(actual_audio_dur)
        composite.write_videofile(final_out, codec="libx264", audio_codec="aac",
            audio_bitrate="192k", preset="fast", fps=30, threads=4, logger="bar")
        sz = os.path.getsize(final_out)/1024**2
        mlog("  FINALE: %s (%.1fMB)" % (os.path.basename(final_out), sz))
    
    await make_final(dur_yunxi, concat_y_txt, "yunxi")
    await make_final(dur_aixia, concat_a_txt, "aixia")
    
    mlog("\n完成！桌面：")
    mlog("  成品_素材01_45s_v14_yunxi.mp4")
    mlog("  成品_素材01_45s_v14_aixia.mp4")

if __name__ == "__main__":
    asyncio.run(main())
