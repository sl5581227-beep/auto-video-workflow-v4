#!/usr/bin/env python3
import subprocess, os, shutil

FINAL = r'C:\Users\Administrator\Desktop\成品_素材01.mp4'
ASS = r'C:\Users\Administrator\Desktop\subs_v3.ass'
OUT = r'C:\Users\Administrator\Desktop\成品_素材01_final.mp4'

# Copy ASS to ASCII path
ascii_ass = 'C:\\temp_subs.ass'
os.makedirs('C:\\', exist_ok=True)
shutil.copy2(ASS, ascii_ass)
print('Copied ASS to:', ascii_ass)

# FFmpeg ASS filter: use escaped colon C\:/path
# In FFmpeg filter syntax: C\:/temp_subs.ass means drive C, path /temp_subs.ass
# Using raw string in Python
vf_filter = r"ass=C\:/temp_subs.ass"
cmd = [
    'ffmpeg', '-i', FINAL,
    '-vf', vf_filter,
    '-c:a', 'copy',
    '-y', OUT
]
print('VF filter:', vf_filter)
print('Full command:', ' '.join(['ffmpeg', '-i', 'C:\\Users\\...', '-vf', vf_filter, '-c:a', 'copy', '-y', 'C:\\Users\\...']))

r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
print('RC:', r.returncode)
if r.returncode != 0:
    lines = r.stderr.strip().split('\n')
    for l in lines[-15:]:
        print('ERR:', l)
else:
    sz = os.path.getsize(OUT) // 1024 // 1024
    print(f'SUCCESS! Size: {sz} MB')
    
    # Verify streams
    r2 = subprocess.run(['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', OUT],
                       capture_output=True, text=True)
    import json
    try:
        data = json.loads(r2.stdout)
        for s in data.get('streams', []):
            lang = s.get('tags', {}).get('language', '?')
            print(f'  [{s["index"]}] {s["codec_type"]}: {s.get("codec_name")} (lang={lang})')
    except:
        pass
