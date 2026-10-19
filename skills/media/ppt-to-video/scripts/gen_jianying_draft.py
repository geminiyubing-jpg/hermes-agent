#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成剪映草稿：底片（无字幕无人声）+ 550 条字幕文本轨（按原声时间排好）。
用途：剪映里全选字幕 → 朗读 → 解说小美（换女声），字幕时间即原声时间。
用法: gen_jianying_draft.py <timeline.json> <plate.mp4> <staging_dir> <draft_name>"""
import json, os, sys

timeline_path, plate_path, staging, name = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
FPS = 30
tl = json.load(open(timeline_path))
TOTAL_F = tl["totalFrames"]

def f2us(f):
    return round(f * 1_000_000 / FPS)

import pyJianYingDraft as draft

folder = draft.DraftFolder(staging)
script = folder.create_draft(name, 1920, 1080, fps=FPS, allow_replace=True)
script.append_track(draft.TrackSpec(draft.TrackType.video, name="底片"))
script.append_track(draft.TrackSpec(draft.TrackType.text, name="字幕"))

# 底片按 25 段切段（source=target，剪映里可单独变速/重排）
plate = draft.VideoMaterial(plate_path)
segs = tl["segments"]
for i, seg in enumerate(segs):
    f0 = round(seg["start"] * FPS)
    f1 = round((segs[i + 1]["start"] if i + 1 < len(segs) else tl["totalSec"]) * FPS)
    rng = draft.Timerange(f2us(f0), f2us(f1) - f2us(f0))
    script.add_segment(draft.VideoSegment(plate, rng, source_timerange=rng), "底片")

# 字幕样式：白字 + 黑描边近似原片（剪映 size ≈ 画布高百分比：52px/10.8 ≈ 4.8）
style = draft.TextStyle(size=4.8, color=(1.0, 1.0, 1.0))
n = 0
for seg in segs:
    for j, ln in enumerate(seg["lines"]):
        f0 = round((seg["start"] + ln["t0"]) * FPS)
        nxt = seg["lines"][j + 1] if j + 1 < len(seg["lines"]) else None
        hard_end = round((seg["start"] + (nxt["t0"] if nxt else ln["t1"])) * FPS) if nxt else round((seg["start"] + ln["t1"]) * FPS)
        f1 = min(round((seg["start"] + ln["t1"]) * FPS), hard_end, TOTAL_F)
        if f1 <= f0:
            continue
        rng = draft.Timerange(f2us(f0), f2us(f1) - f2us(f0))
        script.add_segment(
            draft.TextSegment(ln["s"], rng, style=style,
                              clip_settings=draft.ClipSettings(transform_y=-0.62)),
            "字幕")
        n += 1
script.save()
print(f"draft: {name}, video segs={len(segs)}, text segs={n} → {staging}")
