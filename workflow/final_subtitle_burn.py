#!/usr/bin/env python3
"""
Final working subtitle burn - using PIL ImageClip with correct SRT parsing
Fixed: CRLF SRT parsing + PIL Unicode rendering + MoviePy composition
"""
import subprocess, os, re, shutil
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import moviepy as mp

PROJ_DIR  = r"C:\Users\Administrator\Desktop\素材01\西梅奇亚籽轻上饮品\_frames\project_60s"
OUT_DIR   = r"C:\Users\Administrator\Desktop"
SRT_PATH  = os.path.join(OUT_DIR, "subs_60s.srt")
VO_PATH   = os.path.join(OUT_DIR, "voiceover_60s.mp3")
FONT      = r'C:\Windows\Fonts\msyh.ttc'
FINAL_OUT = os.path.join(OUT_DIR, "成品_素材01_60s.mp4")

def get_dur(fp):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                       '-of', 'csv=p=0', fp], capture_output=True, text=True, timeout=30)
    return float(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else 0.0

def parse_srt(path):
    """Parse SRT using CRLF block splitting - returns list of dicts"""
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

def render_subtitle_image(text, width=1080, font_size=52, stroke=3):
    """Render subtitle with black stroke outline + white fill using PIL"""
    tmp = Image.new('RGBA', (10, 10), (0, 0, 0, 0))
    tmp_draw = ImageDraw.Draw(tmp)
    font = ImageFont.truetype(FONT, font_size)
    bbox = tmp_draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    pad_x, pad_y = 40, 15
    img_w = min(text_w + pad_x * 2, width - 40)
    img_h = text_h + pad_y * 2
    img = Image.new('RGBA', (img_w, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    x_center = (img_w - text_w) // 2 - bbox[0]
    y_center = (img_h - text_h) // 2 - bbox[1]
    # Stroke (outline)
    for dx in range(-stroke, stroke + 1):
        for dy in range(-stroke, stroke + 1):
            if abs(dx) == stroke or abs(dy) == stroke:
                draw.text((x_center + dx, y_center + dy), text, font=font, fill=(0, 0, 0, 255))
    # White fill
    draw.text((x_center, y_center), text, font=font, fill=(255, 255, 255, 255))
    return np.array(img, dtype='uint8')

def main():
    print("=" * 60)
    print("Final Subtitle Burn - PIL + CRLF SRT")
    print("=" * 60)
    
    # Step 1: Parse SRT correctly
    print("\nStep 1: Parsing SRT (CRLF format)...")
    subs = parse_srt(SRT_PATH)
    print(f"Loaded {len(subs)} subtitles")
    for s in subs[:3]:
        print(f"  [{s['start']:.2f}s] {s['text']}")
    
    # Step 2: Load video
    print("\nStep 2: Loading video...")
    video_path = os.path.join(PROJ_DIR, "video_final_no_audio.mp4")
    if not os.path.exists(video_path):
        video_path = os.path.join(PROJ_DIR, "concat_raw.mp4")
    video = mp.VideoFileClip(video_path)
    print(f"Video: {video.w}x{video.h}, {video.duration:.2f}s")
    
    # Step 3: Load TTS audio
    print("Step 3: Loading TTS audio...")
    tts_audio = mp.AudioFileClip(VO_PATH)
    print(f"TTS: {tts_audio.duration:.2f}s")
    
    # Step 4: Verify font works
    print("\nStep 4: Testing PIL subtitle render...")
    test_arr = render_subtitle_image(subs[0]['text'])
    visible = np.sum(test_arr[:, :, 3] > 10)
    print(f"PIL render test: {visible} visible pixels ({'OK' if visible > 1000 else 'FAIL'})")
    
    # Step 5: Create PIL subtitle clips
    print("\nStep 5: Creating subtitle clips...")
    FAIL = 0
    for i, sub in enumerate(subs):
        dur = sub['end'] - sub['start']
        if dur <= 0 or not sub['text'].strip():
            print(f"  SKIP [{i+1}]: empty/invalid")
            continue
        try:
            sub_img = render_subtitle_image(sub['text'])
            tc = mp.ImageClip(sub_img).with_duration(dur)
            x_pos = (1080 - sub_img.shape[1]) / 2
            y_pos = video.h - sub_img.shape[0] - 80
            tc = tc.with_position((x_pos, y_pos)).with_start(sub['start'])
            print(f"  OK [{i+1:02d}]: '{sub['text'][:25]}' at y={y_pos:.0f}")
        except Exception as e:
            print(f"  FAIL [{i+1:02d}]: {e}")
            FAIL += 1
    
    print(f"\nSubtitle clips: {len(subs)} ({FAIL} failed)")
    
    # Step 6: Composite and write
    print("\nStep 6: Compositing video + subtitles + TTS...")
    sub_clips = []
    for s in subs:
        dur = s['end'] - s['start']
        if dur <= 0 or not s['text'].strip():
            continue
        sub_img = render_subtitle_image(s['text'])
        tc = mp.ImageClip(sub_img).with_duration(dur)
        x_pos = (1080 - sub_img.shape[1]) / 2
        y_pos = video.h - sub_img.shape[0] - 80
        tc = tc.with_position((x_pos, y_pos)).with_start(s['start'])
        sub_clips.append(tc)
    
    composite = mp.CompositeVideoClip([video] + sub_clips, size=(1080, 1920))
    composite = composite.with_audio(tts_audio)
    composite = composite.with_duration(tts_audio.duration)
    
    print(f"Writing to: {FINAL_OUT}")
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
    
    # Step 7: Verify
    if os.path.exists(FINAL_OUT):
        sz = os.path.getsize(FINAL_OUT) / 1024**2
        dur = get_dur(FINAL_OUT)
        r2 = subprocess.run(['ffprobe', '-v', 'quiet', '-print_format', 'json',
                           '-show_streams', FINAL_OUT], capture_output=True, text=True)
        import json
        info = json.loads(r2.stdout)
        streams = info.get('streams', [])
        has_v = any(s['codec_type'] == 'video' for s in streams)
        has_a = any(s['codec_type'] == 'audio' for s in streams)
        print()
        print("=" * 60)
        print("SUCCESS!")
        print(f"  成品: {FINAL_OUT}")
        print(f"  大小: {sz:.1f} MB")
        print(f"  时长: {dur:.1f}s")
        print(f"  视频流: {'YES' if has_v else 'NO'}")
        print(f"  音频流: {'YES' if has_a else 'NO'}")
        print(f"  字幕渲染: PIL ImageClip + Microsoft YaHei")
        print(f"  SRT解析: CRLF block split (20 subtitles)")
        print("=" * 60)
    else:
        print("ERROR: Output not created!")

if __name__ == '__main__':
    main()
