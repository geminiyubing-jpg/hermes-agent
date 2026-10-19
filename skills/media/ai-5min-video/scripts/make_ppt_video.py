# -*- coding: utf-8 -*-
"""PPT 直出配音视频：PPT 截图 + 逐句 TTS + PIL 字幕 + concat
4:3 · 1440×1080 · 字幕绘制在 PPT 预留的底部字幕区
"""
import asyncio
import os
import re
import subprocess

from PIL import Image, ImageDraw, ImageFont

import edge_tts

BASE = "/Volumes/DATA/hermes-agent-main/mywork/ai_ep01"
VID = f"{BASE}/vid"
SCRIPT = "/Users/yubing-macmini/Movies/andy_materials/AI演化论_前十期讲解稿_审阅版.md"
VOICE = "zh-CN-YunyangNeural"
RATE = "+14%"
TAIL = 0.45
OUT_W, OUT_H = 1440, 1080
FONT_PATH = "/System/Library/Fonts/Supplemental/Songti.ttc"


def parse_segments():
    text = open(SCRIPT, encoding="utf-8").read()
    ep01 = text.split("# EP01")[1].split("# EP02")[0]
    marks = [(int(m.group(1)), m.end()) for m in
             re.finditer(r"【(\d+)\|30秒\|[^】\n]*】", ep01)]
    segs = {}
    for k, (n, end) in enumerate(marks):
        stop = marks[k + 1][1] if k + 1 < len(marks) else len(ep01)
        body = ep01[end:stop]
        body = re.split(r"\n\s*\n---", body)[0].strip()
        segs[n] = body
    assert len(segs) == 10, f"got {len(segs)} segments"
    return segs


def split_sentences(t):
    t = t.replace("\n", "")
    return [p.strip() for p in re.split(r"(?<=[。？！；])", t) if p.strip() and len(p.strip()) >= 2]


def dur(p):
    return float(subprocess.check_output(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", p]).decode().strip())


async def tts(sentences):
    os.makedirs(f"{VID}/sent", exist_ok=True)
    sem = asyncio.Semaphore(4)

    async def one(i, s, mp3):
        if os.path.exists(mp3) and os.path.getsize(mp3) > 500:
            return
        async with sem:
            for a in range(3):
                try:
                    await edge_tts.Communicate(s, VOICE, rate=RATE).save(mp3)
                    return
                except Exception:
                    if a == 2:
                        raise
                    await asyncio.sleep(2)
    jobs = [(i, s, f"{VID}/sent/s{i:03d}.mp3") for i, s in enumerate(sentences)]
    await asyncio.gather(*(one(*j) for j in jobs))


def wrap(text, font, max_w, draw):
    lines, cur = [], ""
    for ch in text:
        if draw.textlength(cur + ch, font=font) <= max_w:
            cur += ch
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines


def sub_image(seg_idx, sub_text, out):
    """幻灯片 + 底部字幕：单行，贴最底部，超长自动缩字号"""
    src = f"{VID}/slide-{seg_idx:02d}.png"
    im = Image.open(src).convert("RGB")
    d = ImageDraw.Draw(im)
    max_w = int(OUT_W * 0.94)
    fs = 48
    while fs > 24:
        font = ImageFont.truetype(FONT_PATH, fs)
        if d.textlength(sub_text, font=font) <= max_w:
            break
        fs -= 2
    font = ImageFont.truetype(FONT_PATH, fs)
    w = d.textlength(sub_text, font=font)
    x = (OUT_W - w) / 2
    y = OUT_H - int(fs * 1.35)  # 贴最底部
    d.text((x + 2, y + 2), sub_text, font=font, fill=(8, 12, 20))
    d.text((x, y), sub_text, font=font, fill=(247, 250, 255))
    im.save(out)


def main():
    segs = parse_segments()
    sentences = []  # (seg_idx, text)
    for n in range(1, 11):
        for s in split_sentences(segs[n]):
            sentences.append((n, s))
    print(f"{len(sentences)} 句")
    asyncio.run(tts([s for _, s in sentences]))

    os.makedirs(f"{VID}/imgs", exist_ok=True)
    seg_files = []
    for i, (n, s) in enumerate(sentences):
        img = f"{VID}/imgs/i{i:03d}.png"
        if not os.path.exists(img):
            sub_image(n, s, img)
        d = dur(f"{VID}/sent/s{i:03d}.mp3") + TAIL
        seg = f"{VID}/seg{i:03d}.ts"
        if not os.path.exists(seg):
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                            "-loop", "1", "-framerate", "30", "-t", f"{d:.3f}", "-i", img,
                            "-i", f"{VID}/sent/s{i:03d}.mp3",
                            "-vf", "scale=1440:1080:flags=lanczos,format=yuv420p",
                            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                            "-c:a", "aac", "-b:a", "160k", "-shortest",
                            "-mpegts_flags", "+resend_headers", "-f", "mpegts", seg],
                           check=True)
        seg_files.append(seg)
    lst = f"{VID}/list.txt"
    open(lst, "w").write("".join(f"file '{s}'\n" for s in seg_files))
    out = f"{BASE}/GPT6来了_AI演化论_EP01_4x3_配音版.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", lst, "-c", "copy", "-movflags", "+faststart", out], check=True)
    total = sum(dur(s) for s in seg_files)
    print(f"DONE {out}  {total/60:.1f} min, {len(seg_files)} 段")


if __name__ == "__main__":
    main()
