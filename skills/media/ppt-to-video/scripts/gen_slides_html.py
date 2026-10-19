#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""slides-html.json → 每页一个独立 HTML 文件（960×540，绝对定位，原配色原字号）。"""
import json, os, html

DATA = json.load(open("/Volumes/DATA/AI-audit/promo-mit-brain/remotion/src/full/slides-html.json"))
OUT = "/Volumes/DATA/AI-audit/promo-mit-brain/slides-html"
os.makedirs(OUT, exist_ok=True)

CSS = """<!DOCTYPE html><html><head><meta charset="utf-8"><style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:960px;height:540px;background:#0E0B1A;overflow:hidden;
  font-family:"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  -webkit-font-smoothing:antialiased}
.slide{position:relative;width:960px;height:540px}
.shape{position:absolute}
.txt{white-space:pre-wrap;line-height:1.35;overflow:hidden}
</style></head><body><div class="slide">
"""

for idx, shapes in DATA["slides"].items():
    parts = [CSS]
    for s in shapes:
        style = f"left:{s['x']}px;top:{s['y']}px;width:{s['w']}px;min-height:{s['h']}px"
        if s.get("fill"):
            style += f";background:{s['fill']}"
        if s.get("line"):
            style += f";border:1px solid {s['line']}"
        if s["shape"] == "AUTO_SHAPE" and s["w"] > 60 and s["h"] > 24:
            style += ";border-radius:10px"
        if s["text"] is not None:
            fw = 700 if (s.get("bold") or (s.get("fs") or 14) >= 22) else 400
            style += f";font-size:{s['fs']}px;font-weight:{fw}"
            if s.get("color"):
                style += f";color:{s['color']}"
            parts.append(f'<div class="shape txt t{len([1 for x in parts if "shape txt" in x])}" style="{style}">{html.escape(s["text"])}</div>\n')
        else:
            style += f";height:{s['h']}px"
            parts.append(f'<div class="shape" style="{style}"></div>\n')
    parts.append("""</div><script>
const n = new URLSearchParams(location.search).get('n');
if (n !== null) document.querySelectorAll('.txt').forEach(el => {
  const k = parseInt(el.className.match(/t(\d+)/)[1]);
  el.style.visibility = k < parseInt(n) ? 'visible' : 'hidden';
});
</script></body></html>""")
    open(f"{OUT}/slide-{int(idx):02d}.html", "w").write("".join(parts))

print("written:", len(DATA["slides"]), "files →", OUT)
