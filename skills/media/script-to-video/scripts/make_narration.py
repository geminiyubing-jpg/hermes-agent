# -*- coding: utf-8 -*-
"""从逐页稿提取口播文案并生成 TTS 配音"""
import asyncio
import json
import re
import os
import sys

import edge_tts

SRC = "/Volumes/DATA/ppt-master-main/projects/qian_ep01_ppt169_20260909/sources/EP01_钱是什么_逐页稿v4_审批版.md"
OUT = "/Volumes/DATA/hermes-agent-main/mywork/money_pptx/video"
VOICE = "zh-CN-YunjianNeural"  # 纪录片男声
RATE = "-8%"  # 稍慢，解说节奏


def parse_pages():
    text = open(SRC, encoding="utf-8").read()
    pages = []
    blocks = re.split(r"\n## 第(\d+)页", text)
    for i in range(1, len(blocks), 2):
        num = int(blocks[i])
        body = blocks[i + 1]
        m = re.search(r"【口播】(.+?)(?=\n## |\n---|\Z)", body, re.S)
        if not m:
            continue
        oral = m.group(1).strip()
        pages.append((num, oral))
    return pages


async def synth(num, oral):
    mp3 = os.path.join(OUT, f"audio/p{num:02d}.mp3")
    if os.path.exists(mp3) and os.path.getsize(mp3) > 1000:
        return mp3
    # 口播里的引号等符号朗读无碍；去掉 markdown 痕迹
    clean = oral.replace("**", "")
    tts = edge_tts.Communicate(clean, VOICE, rate=RATE)
    await tts.save(mp3)
    return mp3


async def main():
    os.makedirs(os.path.join(OUT, "audio"), exist_ok=True)
    pages = parse_pages()
    print(f"parsed {len(pages)} pages")
    for num, oral in pages:
        mp3 = await synth(num, oral)
        print(f"p{num:02d} -> {os.path.basename(mp3)} ({os.path.getsize(mp3)//1024}KB)")
    json.dump({str(n): o for n, o in pages}, open(os.path.join(OUT, "oral.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    asyncio.run(main())
