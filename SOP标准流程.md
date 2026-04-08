# 半自动剪辑体系 SOP 标准流程 v4.8

## 流程总览

```
产品信息分析 → 爆款文案解读 → 镜头分析 → 脚本创作 
    → 智能匹配 → 素材预处理 → 专业剪辑 → 字幕生成 
    → TTS配音 → 混流封装 → QC质检
```

---

## Step 1: 产品分析

### 输入
- 产品信息文档（.md/.txt）
- 爆款文案参考（.xlsx）

### 操作
1. 提取产品核心卖点（至少5条）
2. 提取目标用户画像
3. 提取情绪价值关键词
4. 提取爆款文案结构规律

### 输出
```
产品核心卖点：xxx
目标用户：xxx
情绪价值：xxx
文案结构：黄金3秒 + 卖点 + 信任背书 + 强CTA
```

---

## Step 2: 镜头分析

### 输入
- 原始素材文件夹（含416个.MOV文件）
- 产品镜头索引.csv

### 操作
1. 遍历所有镜头文件
2. 提取关键帧（逐秒JPG）
3. 视觉分析每个镜头内容：
   - 产品特写 / 场景演示 / 空镜头 / 人物
   - 近景 / 中景 / 远景
   - 室内 / 户外
4. 按类型打标签：
   - 产品展示 → 开场钩子、产品特写
   - 产品场景A → 功效说明
   - 产品场景B → 使用场景
   - 人群场景 → 信任背书、社交证明

### 输出
`lens_analysis_report.json`

---

## Step 3: 脚本创作

### 规则
- 长度：12-120秒（目标60秒约20句）
- 结构：黄金3秒 → 核心卖点 → 信任背书 → 强CTA
- 风格：口语化、有网感、无AI味
- 每句长度：10-20字

### 输出
`script_v2.txt`

### 拟人化自检
- [ ] 有无"管不住嘴"、"遭不住"类口语词
- [ ] 有无"所以"、"关键是"类连接词
- [ ] 感叹号是否制造停顿强调
- [ ] 数字是否具体（十六颗、零脂肪）
- [ ] CTA是否有紧迫感

---

## Step 4: 智能匹配镜头

### 规则
| 脚本段落 | 推荐镜头类型 |
|----------|-------------|
| 黄金3秒/共鸣 | 人群场景 |
| 产品引入/报品名 | 产品展示 |
| 成分/功效 | 产品场景A/B |
| 口感/体验 | 产品展示 |
| 使用场景 | 室内/产品场景B |
| 信任背书 | 人群场景/达人场景 |
| CTA | 产品展示 |

### 输出
`clip_script_match.json`

---

## Step 5: 素材预处理

### 命令
```bash
ffmpeg -i input.mov \
  -an \                           # 去除音频
  -c:v libx264 -preset fast -crf 22 \
  -vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black" \
  -r 30 \
  output.mp4
```

### 输出
`clips_processed/` 文件夹

---

## Step 6: 视频剪辑拼接

```bash
# 生成拼接列表
echo "file 'clip_00.mp4'" > concat.txt
echo "file 'clip_01.mp4'" >> concat.txt

ffmpeg -f concat -safe 0 -i concat.txt \
  -c:v libx264 -preset fast -crf 20 \
  -an \
  concat_raw.mp4
```

---

## Step 7: TTS配音生成

```python
import edge_tts

async def gen_tts():
    communicate = edge_tts.Communicate(
        "完整脚本文字",
        voice="zh-CN-XiaoxiaoNeural",
        rate="+5%",
        pitch="-3Hz",
    )
    await communicate.save("voiceover.mp3")
```

---

## Step 8: 字幕生成

### 时间轴计算
```
总时长 = TTS实际时长
每句时长 = 字符数 × (总时长 / 总字符数) × 1.05
```

### SRT格式
```
1
00:00:00,000 --> 00:00:03,400
第一句字幕

2
00:00:03,500 --> 00:00:06,800
第二句字幕
```

---

## Step 9: 混流封装（关键）

### 问题
FFmpeg subtitles filter在Windows上对 `C:\path` 冒号处理错误。

### 解决方案：MoviePy烧录

```python
import moviepy as mp

video = mp.VideoFileClip("concat_raw.mp4")
tts_audio = mp.AudioFileClip("voiceover.mp3")

# 创建字幕TextClip
sub_clips = []
for start, end, text in subtitles:
    tc = mp.TextClip(
        text=text,
        font="C:/Windows/Fonts/arial.ttf",
        font_size=52,
        color='white',
        stroke_color='black',
        stroke_width=3,
        duration=end-start
    )
    tc = tc.with_position(('center', 'bottom'))
    tc = tc.with_start(start)
    sub_clips.append(tc)

# 合成
composite = mp.CompositeVideoClip([video] + sub_clips, size=(1080, 1920))
composite = composite.with_audio(tts_audio)  # 用TTS，不用video.audio！
composite.write_videofile("成品.mp4", codec='libx264', audio_codec='aac')
```

---

## Step 10: QC质检

### 10维度评分

| 维度 | 满分 | 及格线 |
|------|------|--------|
| 与脚本匹配度 | 20 | 14 |
| 剪辑节奏与转场 | 15 | 10 |
| 配音真实感 | 15 | 9 |
| 字幕准确性 | 10 | 7 |
| 镜头选择合理性 | 15 | 10 |
| 视觉连贯性 | 10 | 6 |
| 内容合规性 | 5 | 4 |
| 品牌与产品信息准确性 | 5 | 3 |
| 完播率预估 | 5 | 3 |
| 文件技术规格 | 否决项 | - |

### 技术规格（否决项）
- 分辨率：1080×1920（9:16）❌ 直接否决
- 编码：H264 + AAC
- 时长偏差：±5秒内

---

## 注意事项

1. **音频一定要单独加载TTS**，不要用video.audio（可能无音轨）
2. **字幕烧录用MoviePy**，不要用FFmpeg subtitles filter（Windows路径bug）
3. **镜头预处理必须用`-an`**，彻底去除原始背景音
4. **成品视频用TTS时长截断**，确保音画同步
