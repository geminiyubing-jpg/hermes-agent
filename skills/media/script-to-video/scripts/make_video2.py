# -*- coding: utf-8 -*-
"""逐句流水线：解说词 → 分句 → 每句 TTS + 每句截图(字幕内嵌) → 逐句 ts → concat
横竖两版。字幕随 HTML 美学系统渲染，无需 ffmpeg 文本滤镜。
用法:
  python make_video2.py land|port|both [pageStart]
"""
import asyncio
import json
import os
import re
import subprocess
import sys
import urllib.parse

import edge_tts

BASE = "/Volumes/DATA/hermes-agent-main/mywork/money_pptx/video"
HTML = "/Volumes/DATA/hermes-agent-main/mywork/money_pptx/钱是什么_王朝的钱袋子_EP01.html"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
VOICE = "zh-CN-YunyangNeural"
RATE = "+6%"
TAIL = 0.45  # 每句尾部停顿


def split_sentences(oral):
    oral = oral.replace("\n", "").replace("**", "")
    parts = re.split(r"(?<=[。？！；])", oral)
    return [p.strip() for p in parts if p.strip() and len(p.strip()) >= 2]


def dur(p):
    return float(subprocess.check_output(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", p]).decode().strip())


async def tts_pages(pages):
    os.makedirs(f"{BASE}/sent", exist_ok=True)
    jobs = []
    for num, oral in pages:
        for i, s in enumerate(split_sentences(oral)):
            mp3 = f"{BASE}/sent/p{num:02d}_s{i:02d}.mp3"
            if not (os.path.exists(mp3) and os.path.getsize(mp3) > 500):
                jobs.append((num, i, s, mp3))
    sem = asyncio.Semaphore(4)

    async def one(num, i, s, mp3):
        async with sem:
            for attempt in range(3):
                try:
                    tts = edge_tts.Communicate(s, VOICE, rate=RATE)
                    await tts.save(mp3)
                    return
                except Exception as e:
                    if attempt == 2:
                        raise
                    await asyncio.sleep(2)

    await asyncio.gather(*(one(*j) for j in jobs))
    # 索引
    idx = []
    for num, oral in pages:
        sents = split_sentences(oral)
        idx.append({"page": num, "sents": [
            {"i": i, "text": s, "mp3": f"{BASE}/sent/p{num:02d}_s{i:02d}.mp3"}
            for i, s in enumerate(sents)]})
    json.dump(idx, open(f"{BASE}/sent_index.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


def shot(orientation, page, text, out):
    portrait = orientation == "port"
    size = "1080,1920" if portrait else "1920,1080"
    h = f"#static&video&p={page}"
    if portrait:
        h += "&portrait"
    if text:
        h += "&sub=" + urllib.parse.quote(text)
    subprocess.run([CHROME, "--headless", "--disable-gpu",
                    f"--screenshot={out}", f"--window-size={size}",
                    "--hide-scrollbars", f"file://{HTML}{h}"],
                   check=True, capture_output=True)


def build(orientation):
    portrait = orientation == "port"
    size = "1080:1920" if portrait else "1920:1080"
    imgdir = f"{BASE}/imgs_{orientation}"
    os.makedirs(imgdir, exist_ok=True)
    idx = json.load(open(f"{BASE}/sent_index.json"))
    segs = []
    for pg in idx:
        num = pg["page"]
        for s in pg["sents"]:
            img = f"{imgdir}/p{num:02d}_s{s['i']:02d}.png"
            if not os.path.exists(img):
                shot(orientation, num, s["text"], img)
            d = dur(s["mp3"]) + TAIL
            seg = f"{BASE}/seg_{orientation}_{num:02d}_{s['i']:02d}.ts"
            if not os.path.exists(seg):
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                                "-loop", "1", "-framerate", "30", "-t", f"{d:.3f}", "-i", img,
                                "-i", s["mp3"],
                                "-vf", f"scale={size}:flags=lanczos,format=yuv420p",
                                "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                                "-c:a", "aac", "-b:a", "160k", "-shortest",
                                "-mpegts_flags", "+resend_headers", "-f", "mpegts", seg],
                               check=True)
            segs.append(seg)
    lst = f"{BASE}/list_{orientation}.txt"
    open(lst, "w").write("".join(f"file '{s}'\n" for s in segs))
    out = f"/Volumes/DATA/hermes-agent-main/mywork/money_pptx/钱是什么_EP01_{'竖版' if portrait else '横版'}.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", lst, "-c", "copy",
                    "-movflags", "+faststart", out], check=True)
    total = sum(dur(s) for s in segs)
    print(f"{orientation} DONE: {out}  {total/60:.1f} min, {len(segs)} 段")


if __name__ == "__main__":
    pages = sorted(((int(k), v) for k, v in
                    json.load(open(f"{BASE}/oral.json")).items()))
    asyncio.run(tts_pages(pages))
    which = sys.argv[1] if len(sys.argv) > 1 else "both"
    if which in ("land", "both"):
        build("land")
    if which in ("port", "both"):
        build("port")
