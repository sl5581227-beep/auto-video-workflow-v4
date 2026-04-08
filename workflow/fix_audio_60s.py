#!/usr/bin/env python3
"""
修复60秒版本的音频问题：
Step 6截断时用-an去掉了静音音轨
Step 7 MoviePy用的是video.audio（无音轨）
需要：手动加载TTS作为音频源
"""
import subprocess, json, os, re

PROJ_DIR  = r"C:\Users\Administrator\Desktop\素材01\西梅奇亚籽轻上饮品\_frames\project_60s"
OUT_DIR   = r"C:\Users\Administrator\Desktop"
VO_PATH   = os.path.join(OUT_DIR, "voiceover_60s.mp3")
SRT_PATH  = os.path.join(OUT_DIR, "subs_60s.srt")
FINAL_OUT = os.path.join(OUT_DIR, "成品_素材01_60s.mp4")

# Check if files exist
print("Checking files:")
print(f"  TTS: {VO_PATH} {'OK' if os.path.exists(VO_PATH) else 'MISSING'}")
print(f"  SRT: {SRT_PATH} {'OK' if os.path.exists(SRT_PATH) else 'MISSING'}")
print(f"  Final: {FINAL_OUT} {'OK' if os.path.exists(FINAL_OUT) else 'MISSING'}")

def get_dur(fp):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                       '-of', 'csv=p=0', fp], capture_output=True, text=True, timeout=30)
    if r.returncode == 0 and r.stdout.strip():
        return float(r.stdout.strip())
    return 0.0

vo_dur = get_dur(VO_PATH)
print(f"  TTS duration: {vo_dur:.2f}s")

# Load video WITHOUT audio (use -an to prevent audio loading)
import moviepy as mp

# The issue: final video was created with -an so it has no audio
# We need to load the video and ADD the TTS audio
final_video_path = os.path.join(PROJ_DIR, "video_final_no_audio.mp4")
if not os.path.exists(final_video_path):
    # Try concat raw
    final_video_path = os.path.join(PROJ_DIR, "concat_raw.mp4")
    
print(f"Loading video from: {final_video_path}")

# Load video with audio=False to avoid errors
video = mp.VideoFileClip(final_video_path)
video_dur = video.duration
print(f"Video: {video.w}x{video.h}, {video_dur:.2f}s")

# Load TTS as audio
tts_audio = mp.AudioFileClip(VO_PATH)
tts_dur = tts_audio.duration
print(f"TTS audio: {tts_dur:.2f}s")

# Parse SRT
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

subs = parse_srt(SRT_PATH)
print(f"Loaded {len(subs)} subtitles")

# Find font
font_path = None
for fp in [r'C:\Windows\Fonts\arial.ttf', r'C:\Windows\Fonts\simhei.ttf', r'C:\Windows\Fonts\msyh.ttc']:
    if os.path.exists(fp):
        font_path = fp
        print(f"Font: {fp}")
        break

# Create subtitle clips
sub_clips = []
for i, sub in enumerate(subs):
    dur = sub['end'] - sub['start']
    if dur <= 0:
        continue
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
            size=(1080-80, None),
            method='label',
            duration=dur
        )
        x_pos = (1080 - tc.w) / 2
        y_pos = video.h - tc.h - 80
        tc = tc.with_position((x_pos, y_pos))
        tc = tc.with_start(sub['start'])
        sub_clips.append(tc)
        print(f"  Sub [{i+1}]: '{text[:15]}...' OK ({sub['start']:.1f}-{sub['end']:.1f}s)")
    except Exception as e:
        print(f"  Sub [{i+1}] FAIL: {e}")

print(f"Created {len(sub_clips)} subtitle clips")

# Composite: video + subtitle clips + TTS audio
print("Compositing video + subtitles + TTS audio...")
composite = mp.CompositeVideoClip([video] + sub_clips, size=(1080, 1920))

# CRITICAL: Set TTS as the audio (not the silent video audio)
composite = composite.with_audio(tts_audio)
composite = composite.with_duration(tts_dur)

print(f"Writing final video (duration: {tts_dur:.2f}s)...")

OUT_TMP = os.path.join(OUT_DIR, "成品_素材01_60s_tmp.mp4")
composite.write_videofile(
    OUT_TMP,
    codec='libx264',
    audio_codec='aac',
    audio_bitrate='192k',
    preset='fast',
    fps=30,
    threads=4,
    logger='bar'
)

# Verify
if os.path.exists(OUT_TMP):
    sz = os.path.getsize(OUT_TMP) / 1024**2
    final_dur = get_dur(OUT_TMP)
    
    r2 = subprocess.run(['ffprobe', '-v', 'quiet', '-print_format', 'json',
                       '-show_streams', OUT_TMP], capture_output=True, text=True)
    info = json.loads(r2.stdout)
    streams = info.get('streams', [])
    has_v = any(s['codec_type'] == 'video' for s in streams)
    has_a = any(s['codec_type'] == 'audio' for s in streams)
    
    print()
    print("=" * 55)
    print(f"  成品: {OUT_TMP}")
    print(f"  大小: {sz:.1f} MB")
    print(f"  时长: {final_dur:.1f}s")
    print(f"  视频流: {'YES' if has_v else 'NO'}")
    print(f"  音频流: {'YES' if has_a else 'NO'}")
    print("=" * 55)
    
    # Replace final
    FINAL_OUT2 = os.path.join(OUT_DIR, "成品_素材01_60s.mp4")
    if os.path.exists(FINAL_OUT2):
        os.remove(FINAL_OUT2)
    os.rename(OUT_TMP, FINAL_OUT2)
    print(f"Renamed to: {FINAL_OUT2}")
else:
    print("FAILED: Output not created!")
