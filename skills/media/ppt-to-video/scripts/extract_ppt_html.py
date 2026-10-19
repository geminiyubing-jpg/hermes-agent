#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PPT→HTML 素材提取：全部形状（几何+填充+文字+字号+字色），1pt=1px 的 960×540 逻辑版心。
产出 slides-html.json，Remotion 按原始几何 1:1 重建，保证与 PPT 布局一致不互相遮挡。"""
import json
from pptx import Presentation
from pptx.util import Emu

PPTX = "/Users/yubing-macmini/Downloads/大模型里长出了一个脑_论文深度解构_25页.pptx"
OUT = "/Volumes/DATA/AI-audit/promo-mit-brain/remotion/src/full/slides-html.json"

p = Presentation(PPTX)
SW, SH = p.slide_width, p.slide_height

def emu2px(v):
    return round(Emu(v).pt, 1)  # 1pt = 1px 逻辑版心

def fill_alpha(sh):
    """从填充 XML 读透明度（a:solidFill/a:srgbClr/a:alpha val=百分比*1000）。"""
    try:
        from pptx.oxml.ns import qn
        sp = sh._element
        for sf in sp.iter(qn('a:solidFill')):
            for clr in sf:
                for a in clr.findall(qn('a:alpha')):
                    return int(a.get('val', '100000')) / 100000.0
    except Exception:
        pass
    return 1.0

def fill_info(sh):
    """返回 CSS background / borderColor（尽力而为，取不到给 None）"""
    try:
        f = sh.fill
        if f.type == 1 and f.fore_color and f.fore_color.type == 1:  # solid + RGB
            hexv = str(f.fore_color.rgb)
            a = fill_alpha(sh)
            if a < 0.99:
                r, g, b = int(hexv[0:2], 16), int(hexv[2:4], 16), int(hexv[4:6], 16)
                return f"rgba({r},{g},{b},{round(a,3)})"
            return f"#{hexv}"
        if f.type == 5:  # background (inherit)
            return None
        if f.type is None or f.type == 5:
            return None
    except Exception:
        pass
    return None

def line_info(sh):
    try:
        ln = sh.line
        if ln.fill.type == 1 and ln.color and ln.color.type == 1:
            return f"#{ln.color.rgb}"
    except Exception:
        pass
    return None

def run_props(tf):
    """首个有字号/字色的 run：返回 (fs_pt|None, css_color|None, bold)"""
    fs = color = None
    bold = False
    try:
        for para in tf.paragraphs:
            for run in para.runs:
                if fs is None and run.font.size:
                    fs = run.font.size.pt
                if run.font.bold:
                    bold = True
                if color is None and run.font.color and run.font.color.type == 1:
                    color = f"#{run.font.color.rgb}"
                if fs and color:
                    return fs, color, bold
    except Exception:
        pass
    return fs, color, bold

def iter_shapes(shapes):
    for sh in shapes:
        if sh.shape_type == 6:
            yield from iter_shapes(sh.shapes)
        else:
            yield sh

def slide_shapes(slide):
    out = []
    for sh in iter_shapes(slide.shapes):
        try:
            geo = {"x": emu2px(sh.left), "y": emu2px(sh.top), "w": emu2px(sh.width), "h": emu2px(sh.height)}
        except Exception:
            continue
        if geo["w"] <= 0 or geo["h"] <= 0:
            continue
        item = {
            **geo,
            "shape": str(sh.shape_type).split(" ")[0] if sh.shape_type is not None else "None",
            "fill": fill_info(sh),
            "line": line_info(sh),
            "text": None, "fs": None, "color": None, "bold": False,
        }
        if sh.has_text_frame and sh.text_frame.text.strip():
            t = sh.text_frame.text.rstrip()
            fs, color, bold = run_props(sh.text_frame)
            item["text"] = t
            item["fs"] = round(fs, 1) if fs else max(10.0, round(geo["h"] / max(1, t.count("\n") + 1) * 0.6, 1))
            item["color"] = color
            item["bold"] = bold
        # 无文字且无填充的细线形状也保留（分隔线）
        if item["text"] is None and item["fill"] is None and item["line"] is None:
            if not (item["h"] <= 3 or item["w"] <= 3):
                continue
        out.append(item)
    # 保持 PPT 文档顺序（z 序正确性优先于阅读顺序；入场错峰在渲染层单独编号）
    return out

doc = {}
for i, s in enumerate(p.slides, 1):
    doc[str(i)] = slide_shapes(s)

json.dump({"w": emu2px(SW), "h": emu2px(SH), "slides": doc}, open(OUT, "w"), ensure_ascii=False)
print("slide px:", emu2px(SW), emu2px(SH), "| slides:", len(doc), "| shapes:", sum(len(v) for v in doc.values()))
