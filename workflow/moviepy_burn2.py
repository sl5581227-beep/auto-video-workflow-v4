#!/usr/bin/env python3
"""
MoviePy字幕烧录 - 将SRT字幕渲染为视频TextClip叠加层
"""
import subprocess, os, re, json, sys

FINAL = r'C:\Users\Administrator\Desktop\成品_素材01.mp4'
SRT = r'C:\Users\Administrator\Desktop\subs_v3.srt'
OUT = r'C:\Users\Administrator\Desktop\成品_素材01_final.mp4'

def get_dur(fp):
    try:
        r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                          '-of', 'csv=p=0', fp], capture_output=True, text=True, timeout=30)
        if r.returncode == 0 and r.stdout.strip():
            return float(r.stdout.strip())
    except:
        pass
    return 30.0

# Parse SRT into subtitle entries
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

subs = parse_srt(SRT)
print(f"Loaded {len(subs)} subtitles")

# Load video
print("Loading video...")
import moviepy as mp
import numpy as np

video = mp.VideoFileClip(FINAL)
video_dur = video.duration
print(f"Video: {video.w}x{video.h}, {video_dur:.2f}s")

# Try to find Arial font
font_candidates = [
    r'C:\Windows\Fonts\arial.ttf',
    r'C:\Windows\Fonts\simhei.ttf',
    r'C:\Windows\Fonts\msyh.ttc',
    r'C:\Windows\Fonts\SIMHEI.ttf',
    r'C:\Windows\Fonts\simsun.ttc',
]

font_path = None
for fp in font_candidates:
    if os.path.exists(fp):
        font_path = fp
        print(f"Found font: {fp}")
        break

if font_path is None:
    # Try system default
    print("No preferred font found, will try default")
    font_path = None

# Create subtitle text clips
print("Creating subtitle clips...")
sub_clips = []
failed = 0

for i, sub in enumerate(subs):
    dur = sub['end'] - sub['start']
    if dur <= 0:
        continue
    
    # Clean text - remove trailing punctuation for cleaner display
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
            size=(1080-80, None),  # Width with padding
            method='label',
            duration=dur
        )
        
        # Position at bottom center
        x_pos = (1080 - tc.w) / 2
        y_pos = video.h - tc.h - 80  # 80px from bottom
        
        tc = tc.with_position((x_pos, y_pos))
        tc = tc.with_start(sub['start'])
        sub_clips.append(tc)
        print(f"  [{i+1}] '{text[:20]}...' OK ({sub['start']:.1f}-{sub['end']:.1f}s, {dur:.1f}s)")
        
    except Exception as e:
        print(f"  [{i+1}] FAIL: {e}")
        failed += 1

print(f"\nCreated {len(sub_clips)} subtitle clips ({failed} failed)")

# Composite
print("Compositing...")
composite = mp.CompositeVideoClip([video] + sub_clips, size=(1080, 1920))
composite = composite.with_duration(video_dur)

# Use video's audio
final_audio = video.audio
composite = composite.with_audio(final_audio)

print("Writing video...")
composite.write_videofile(
    OUT,
    codec='libx264',
    audio_codec='aac',
    audio_bitrate='192k',
    preset='fast',
    fps=30,
    threads=4,
    logger='bar',
)

# Verify
if os.path.exists(OUT):
    sz = os.path.getsize(OUT) // 1024 // 1024
    dur = get_dur(OUT)
    print(f"\n{'='*50}")
    print(f"SUCCESS! Output: {OUT}")
    print(f"  Size: {sz} MB")
    print(f"  Duration: {dur:.2f}s")
    print(f"{'='*50}")
else:
    print("FAILED: Output file not created")
