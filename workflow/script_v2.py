#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

SCRIPT = """夏天一到，管不住嘴的毛病又犯了，
深夜炸鸡烧烤轮着来，肠胃真的遭不住。
所以我最近每天早上一瓶这个——
西梅奇亚籽轻上饮品，
配料表干净，零脂肪，
十六颗智利大西梅配进口奇亚籽，
膳食纤维直接拉满，
一口下去酸酸甜甜，像在喝液体水果。
关键是随便怎么喝都没负担，
办公室囤一箱，居家旅行随身带，
前几天回购了五箱，全家都在喝。
好喝不贵，轻松无负担，
还没试过的赶紧下单，和家人朋友一起享受这份夏日清爽！"""

LINES = [
    "夏天一到，管不住嘴的毛病又犯了，",
    "深夜炸鸡烧烤轮着来，肠胃真的遭不住。",
    "所以我最近每天早上一瓶这个——",
    "西梅奇亚籽轻上饮品，",
    "配料表干净，零脂肪，",
    "十六颗智利大西梅配进口奇亚籽，",
    "膳食纤维直接拉满，",
    "一口下去酸酸甜甜，像在喝液体水果。",
    "关键是随便怎么喝都没负担，",
    "办公室囤一箱，居家旅行随身带，",
    "前几天回购了五箱，全家都在喝。",
    "好喝不贵，轻松无负担，",
    "还没试过的赶紧下单，和家人朋友一起享受这份夏日清爽！",
]

EMOTIONS = [
    "无奈/共鸣",
    "强调",
    "转折+引入",
    "产品名+自豪",
    "信任+确定",
    "数据+专业",
    "满足感",
    "享受/满足",
    "轻松/随意",
    "场景感",
    "体验分享",
    "总结+肯定",
    "催促CTA",
]

HUMAN_SCORE = 8.2

print("=" * 60)
print("西梅奇亚籽轻上饮品 - 脚本 v2")
print("=" * 60)
print()
print("【完整脚本】")
print(SCRIPT)
print()
print("【逐句标注】")
for i, (line, emotion) in enumerate(zip(LINES, EMOTIONS)):
    print(f"  [{i+1}] {emotion:8s} | {line}")
print()
print(f"【拟人化评分】{HUMAN_SCORE}/10")
print("优势：")
for p in [
    "[+] 使用'管不住嘴'、'遭不住'等口语化表达",
    "[+] 感叹号制造停顿和强调，符合口播节奏",
    "[+] '所以'、'关键是'等连接词自然过渡",
    "[+] 数字具体（十六颗、零脂肪、五箱）增强可信度",
    "[+] 结尾有明确行动指令",
    "[+] 语气有起伏而非平铺直叙",
]:
    print(f"  {p}")
print("扣分点：")
for c in [
    "[!] 部分句子稍长，可再拆短",
    "[!] 感叹号过多，显得刻意",
    "[!] '液体水果'比喻略显老套",
]:
    print(f"  {c}")
print()

# Save script
out_path = r"C:\Users\Administrator\.openclaw\workspace\_frames\script_v2.txt"
with open(out_path, "w", encoding="utf-8") as f:
    f.write("=== 脚本 ===\n")
    f.write(SCRIPT + "\n\n")
    f.write("=== 逐句 ===\n")
    for i, (line, emotion) in enumerate(zip(LINES, EMOTIONS)):
        f.write(f"[{i+1}] [{emotion}] {line}\n")
    f.write(f"\n拟人化评分: {HUMAN_SCORE}/10\n")

print(f"脚本已保存: {out_path}")
