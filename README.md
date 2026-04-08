# 半自动剪辑体系 4.8

> 本地视频素材 → 成品视频（配音+字幕）的半自动化制作流水线

## 功能概述

将原始视频素材（.MOV/.MP4）自动处理为：
- ✅ 去除原始背景音
- ✅ 智能匹配脚本与镜头
- ✅ 9:16 竖屏输出（1080×1920）
- ✅ TTS中文配音（edge-tts XiaoxiaoNeural）
- ✅ 硬字幕烧录（SRT烧录入画面）
- ✅ 视频拼接与时长对齐

---

## 快速开始

### 环境依赖

```bash
pip install moviepy edge-tts pandas openpyxl Pillow
```

> FFmpeg 需要安装并加入系统 PATH

### 一键运行

```bash
python workflow_60s.py
```

输出：`成品_素材01_60s.mp4`

---

## 项目结构

```
半自动剪辑体系4.8/
├── README.md                          # 本文件
├── 使用指南.md                         # 详细操作说明
├── SOP标准流程.md                      # 标准作业流程
├── QC质检报告模板.md                   # 质量检查标准
│
├── workflow_60s.py                    # 【核心】60秒成品流水线
├── workflow_v3.py                     # 38秒成品流水线
├── script_v2.py                       # 脚本生成工具
├── burn_subtitles.py                  # 字幕烧录工具
├── fix_audio_*.py                     # 音频修复工具
│
├── 素材分析/
│   ├── clip_analysis.csv              # 镜头索引（自动生成）
│   ├── lens_analysis_report.json      # 镜头分析报告（自动生成）
│   └── clip_script_match.json         # 脚本-镜头匹配表（自动生成）
│
├── 配置/
│   └── config_example.json            # 配置示例
│
└── 工作日志/
    └── 2026-04-08_工作日志.md        # 本次工作记录
```

---

## 核心流程图

```
原始素材（.MOV）  →  镜头分析  →  脚本生成  →  镜头匹配
                                          ↓
                                   TTS配音生成
                                          ↓
视频预处理（去音+裁剪） → 拼接 → 截断/对齐配音时长
                                          ↓
                               字幕生成（SRT）
                                          ↓
                            MoviePy烧录字幕 + 混音
                                          ↓
                               成品视频（9:16）
```

---

## 脚本说明

### workflow_60s.py（推荐）
60秒完整流水线，处理时长约5-8分钟。
- 输入：原始素材文件夹 + 脚本内容
- 输出：1080×1920 成品视频

### workflow_v3.py
38秒版本流水线，与60s版本结构一致。

### script_v2.py
脚本生成工具，自动分句、计算时间轴、标注情绪。

### burn_subtitles.py
字幕烧录工具（解决FFmpeg Windows路径bug）。

---

## 常见问题

### Q: FFmpeg subtitles filter报错？
A: 使用`burn_subtitles.py`（MoviePy方案），绕过FFmpeg路径转义问题。

### Q: 视频无声音？
A: 检查是否用了`composite.with_audio(tts_audio)`而非`video.audio`。

### Q: 镜头匹配不准确？
A: 当前基于文件名标签匹配，建议人工审核`clip_script_match.json`。

---

## 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| 4.8 | 2026-04-08 | 完整流水线，60秒成品，MoviePy字幕烧录 |
| 4.7 | 2026-04-08 | 修复FFmpeg subtitles filter路径bug |
| 4.6 | 2026-04-08 | 修复音频混入问题（TTS单独加载） |

---

## 适用场景

- 抖音/ TikTok 产品视频制作
- 直播预热视频
- 电商详情页视频
- 社交媒体短剧

---

*本项目为半自动化工具，最终成片建议人工审核后发布。*
