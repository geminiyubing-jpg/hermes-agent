#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全长版时间轴构建：段起点帧、词级字幕行、关键锚点。产出 src/full/timeline.json"""
import json, subprocess, os, glob

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIO = os.path.join(os.path.dirname(BASE), "audio-full")
OUT = os.path.join(BASE, "src", "full", "timeline.json")
FPS = 30
GAP_S = 0.7  # 段间呼吸
PAD_HEAD = 0.5
TAIL_S = 1.2

def dur(f):
    return float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f]).strip())

# 每段配置：slide、章节、关键词锚点（短语→动画事件）
SEG = [
    ("P01", "slide-01.png", "论文解构", [("大模型里", "hero"), ("四点三倍", "num1"), ("十点三倍", "num2"), ("四十四点三倍", "num3")]),
    ("P02", "slide-02.png", "路线图", []),
    ("P03", "slide-03.png", "第一部分 · 人脑", [("语言网络", "d1"), ("多重需求", "d2"), ("心理理论", "d3"), ("直觉物理", "d4")]),
    ("P04", "slide-04.png", "第一部分 · 人脑", [("趋同演化", "hero"), ("第二个独立诞生的智能系统", "hero2")]),
    ("P05", "slide-05.png", "第二部分 · 实验", [("四十六个任务", "hero")]),
    ("P06", "slide-06.png", "第二部分 · 实验", [("贡献单", "hero"), ("最小对", "chip")]),
    ("P07", "slide-07.png", "第二部分 · 实验", [("脑损伤", "hero")]),
    ("P08", "slide-08.png", "发现一", [("四点三倍", "hero")]),
    ("P09", "slide-09.png", "发现二", [("十点三倍", "hero"), ("四十四点三倍", "hero2")]),
    ("P10", "slide-10.png", "发现三", [("先读题", "chip"), ("后解题", "chip2")]),
    ("P11", "slide-11.png", "对照实验", [("GPT-2", "hero"), ("能力涌现", "chip")]),
    ("P12", "slide-12.png", "第三部分 · 机制", [("省电", "strike"), ("干扰规避", "hero")]),
    ("P13", "slide-13.png", "意义一", [("通用设计图", "hero")]),
    ("P14", "slide-14.png", "意义二", [("新望远镜", "hero")]),
    ("P15", "slide-15.png", "意义三", [("MoE", "hero")]),
    ("P16", "slide-16.png", "局限", []),
    ("P17", "slide-17.png", "一句话总结", [("同构的心智", "hero")]),
    ("P18", "slide-18.png", "深潜 · 方法", [("最小对", "chip")]),
    ("P19", "slide-19.png", "深潜 · 统计", [("三道防线", "hero")]),
    ("P20", "slide-20.png", "深潜 · 对照", [("三合一", "hero")]),
    ("P21", "slide-21.png", "三个启发", []),
    ("P22", "slide-22.png", "五扇门", []),
    ("P23", "slide-23.png", "冷思考", [("比较解剖学", "hero")]),
    ("P24", "slide-24.png", "速查卡", [("四点三倍", "n1"), ("十点三倍", "n2"), ("四十四点三倍", "n3")]),
    ("P25", "slide-25.png", "结语", [("参考答案", "hero"), ("andy", "chip")]),
]

def find_anchor(words, phrase):
    """在词流中找短语首次出现的时间（秒）。"""
    text = "".join(w["w"] for w in words)
    # 重建带 offset 的拼接
    acc = ""
    spans = []  # (char_start, char_end, word_idx)
    for i, w in enumerate(words):
        spans.append((len(acc), len(acc) + len(w["w"]), i))
        acc += w["w"]
    # 短语可能跨词：在 acc 中滑窗
    pos = acc.find(phrase)
    if pos < 0:
        # 宽松：取短语前2字
        pos = acc.find(phrase[:2])
        if pos < 0:
            return None
    for s, e, i in spans:
        if s <= pos < e:
            return words[i]["t"]
    return None

segments = []
t = PAD_HEAD
for pid, slide, chapter, anchors in SEG:
    mp3 = f"{AUDIO}/{pid}.mp3"
    d = dur(mp3)
    words = json.load(open(f"{AUDIO}/{pid}.words.json"))["words"]
    if not words:
        # 兜底：无词级时间戳时按文本线性铺满整段
        import importlib.util
        spec = importlib.util.spec_from_file_location("gen_tts", f"{AUDIO}/gen_tts.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        text = dict((p, t) for p, t in m.SEGMENTS)[pid]
        n = len(text)
        words = [{"t": d * i / n, "d": d / n, "w": ch} for i, ch in enumerate(text)]
        print(f"WARN {pid}: no word boundaries, linear fallback")
    # 字幕行：按标点+长度≤14切
    lines = []
    cur, cur_t0, last_t = [], None, None
    for w in words:
        if cur_t0 is None:
            cur_t0 = w["t"]
        cur.append(w)
        last_t = w["t"] + w["d"]
        s = "".join(x["w"] for x in cur)
        if len(s) >= 13 or (s and s[-1] in "，。？！；：、—"):
            lines.append({"t0": cur_t0, "t1": last_t + 0.15, "s": s})
            cur, cur_t0 = [], None
    if cur:
        lines.append({"t0": cur_t0, "t1": last_t + 0.5, "s": "".join(x["w"] for x in cur)})
    # 词（相对段起点）供卡拉OK高亮
    wrel = [{"t": w["t"], "d": w["d"], "w": w["w"]} for w in words]
    a = {}
    for phrase, ev in anchors:
        at = find_anchor(words, phrase)
        if at is not None:
            a[ev] = round(at, 3)
        else:
            print(f"WARN {pid} anchor not found: {phrase}")
    segments.append({
        "pid": pid, "slide": f"ppt/{slide}", "chapter": chapter,
        "start": round(t, 3), "dur": round(d, 3), "anchors": a,
        "lines": lines, "words": wrel,
    })
    t += d + GAP_S

total = t - GAP_S + TAIL_S
doc = {"fps": FPS, "w": 1080, "h": 1920, "totalSec": round(total, 2),
       "totalFrames": int(total * FPS), "segments": segments}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(doc, open(OUT, "w"), ensure_ascii=False)
print(f"total {total:.1f}s = {doc['totalFrames']} frames, {len(segments)} segments")
