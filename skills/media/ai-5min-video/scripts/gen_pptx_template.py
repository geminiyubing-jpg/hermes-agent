# -*- coding: utf-8 -*-
"""《AI演化论》EP01 · 4:3 满版 PPTX — 设计 v2（最佳实践重写）
原则：一页一观点（行动式标题）· 60-30-10 配色 · 30-40% 留白 ·
     每页一个超大焦点 · 无边框淡填充 · 统一左网格 · 底部留字幕区
"""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn

# ---- 令牌（60-30-10：60 深空底 / 30 白 / 10 电光青）----
BG     = RGBColor(0x0A, 0x0E, 0x1A)
SOFT   = RGBColor(0x11, 0x18, 0x2A)
CYAN   = RGBColor(0x4D, 0xD8, 0xFF)
CYAN_D = RGBColor(0x2E, 0x8F, 0xB8)
VIOLET = RGBColor(0xA7, 0x8B, 0xFA)
INK    = RGBColor(0xF5, 0xF8, 0xFF)
MUTED  = RGBColor(0x8E, 0x9C, 0xB5)
CORAL  = RGBColor(0xFF, 0x6B, 0x5E)
FONT = "PingFang SC"
W, H = Inches(10), Inches(7.5)
ML = Inches(0.75)
CW = Inches(8.5)

prs = Presentation()
prs.slide_width, prs.slide_height = W, H
BLANK = prs.slide_layouts[6]
_pg = [0]


def _ea(run):
    rPr = run._r.get_or_add_rPr()
    ea = rPr.find(qn('a:ea'))
    if ea is None:
        ea = rPr.makeelement(qn('a:ea'), {})
        rPr.append(ea)
    ea.set('typeface', FONT)


def text(sl, x, y, w, h, runs, size=16, color=INK, bold=False,
         align=PP_ALIGN.LEFT, leading=1.3, anchor=MSO_ANCHOR.TOP):
    tb = sl.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    p = tf.paragraphs[0]
    p.alignment = align
    p.line_spacing = leading
    if isinstance(runs, str):
        runs = [(runs, {})]
    for txt, ov in runs:
        r = p.add_run(); r.text = txt
        f = r.font
        f.name = FONT; f.size = Pt(ov.get('size', size))
        f.bold = ov.get('bold', bold); f.color.rgb = ov.get('color', color)
        _ea(r)
    return tb


def rect(sl, x, y, w, h, fill):
    sp = sl.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
    sp.fill.solid(); sp.fill.fore_color.rgb = fill
    sp.line.fill.background(); sp.shadow.inherit = False
    return sp


def slide():
    sl = prs.slides.add_slide(BLANK)
    rect(sl, 0, 0, W, H, BG)
    _pg[0] += 1
    return sl


def kicker(sl, txt):
    text(sl, ML, Inches(0.35), CW, Inches(0.35), txt, size=12, color=CYAN, bold=True)
    rect(sl, ML, Inches(0.78), Inches(0.5), Emu(28575), CYAN)


def title(sl, runs):
    text(sl, ML, Inches(1.0), CW, Inches(1.0), runs, size=26, bold=True, leading=1.25)


def hero(sl, y, num, unit, color=CYAN, size=120, x=ML, w=CW):
    text(sl, x, y, w, Inches(1.7), [(num, {'size': size, 'color': color, 'bold': True}),
                                    (" " + unit, {'size': 26, 'color': color})],
         anchor=MSO_ANCHOR.MIDDLE)


def note(sl, y, runs, size=15, color=MUTED, w=CW, x=ML):
    text(sl, x, y, w, Inches(0.7), runs, size=size, color=color, leading=1.5)


def pageno(sl):
    text(sl, Inches(9.0), Inches(6.9), Inches(0.7), Inches(0.35),
         f"{_pg[0]:02d}", size=11, color=MUTED, align=PP_ALIGN.RIGHT)


# ============ 01 封面：极简大字 ============
s = slide()
text(s, ML, Inches(0.35), CW, Inches(0.4), "AI 演化论 · 第一季 第一期", size=13, color=CYAN, bold=True)
text(s, Inches(0.7), Inches(1.7), Inches(8.6), Inches(2.2),
     [("GPT-6", {'size': 150, 'bold': True}), (" 来了", {'size': 60, 'color': CYAN, 'bold': True})],
     leading=1.0)
rect(s, ML, Inches(4.15), Inches(1.6), Emu(38100), CYAN)
text(s, ML, Inches(4.5), CW, Inches(0.8),
     "AGI 时代真的开始了吗？", size=24, color=INK, bold=True)
note(s, Inches(5.15), "五分钟拆开 GPT-6 —— 它确实来了，但来法跟所有人想的都不一样。", size=15)
text(s, ML, Inches(6.6), CW, Inches(0.35), "讲者 Andy · 9月3日发布 · 5 分钟",
     size=11, color=MUTED)

# ============ 02 ARC：一个数字讲清 ============
s = slide()
kicker(s, "01 / 成绩")
title(s, [("ARC 创纪录，但离 AGI 还差一条地平线", {})])
hero(s, Inches(2.0), "7.78", "%")
for i, (k, v) in enumerate([("来源", "ARC 官方基准"), ("日期", "9月3日"), ("条件", "全自主长任务")]):
    x = ML + Inches(2.95) * i
    text(s, x, Inches(4.15), Inches(2.8), Inches(0.3), k, size=11, color=MUTED)
    text(s, x, Inches(4.5), Inches(2.8), Inches(0.4), v, size=15, color=INK, bold=True)
note(s, Inches(5.25), "ARC 专考真推理：人类轻松满分，AI 常年不及格。", size=15)
note(s, Inches(5.7), [("一句话：革命，进行到百分之七点七八。", {'color': INK, 'bold': True})], size=16)
pageno(s)

# ============ 03 账本：hero -57% ============
s = slide()
kicker(s, "02 / 账本")
title(s, [("发布会看 PPT，账本见真章：", {}), ("更聪明，还更便宜", {'color': CYAN})])
hero(s, Inches(2.0), "-57", "%", color=CYAN)
text(s, ML + Inches(3.4), Inches(2.35), Inches(5.0), Inches(0.5), "单任务成本（对比上一代 Sol）",
     size=15, color=MUTED)
for i, (k, v) in enumerate([("训练", "10万+ GPU · Stargate"), ("推理", "$10–50 / 百万 token"),
                            ("结论", "这次，账本是真好看")]):
    x = ML + Inches(2.95) * i
    text(s, x, Inches(4.3), Inches(2.8), Inches(0.3), k, size=11, color=CYAN if i == 2 else MUTED)
    text(s, x, Inches(4.65), Inches(2.8), Inches(0.6), v, size=14, color=INK, bold=(i == 2))
pageno(s)

# ============ 04 自举：三节点链 ============
s = slide()
kicker(s, "03 / 训练革命")
title(s, [("AI 的进化速度，", {}), ("不再由人类手速决定", {'color': CYAN})])
nodes = [("人类", "写规则 · 做标注", False), ("GPT-5", "带训 · 出数据", False), ("GPT-6", "更强下一代", True)]
for i, (t, sub, hot) in enumerate(nodes):
    x = ML + Inches(3.0) * i
    text(s, x, Inches(2.15), Inches(2.2), Inches(0.7), t, size=34, bold=True,
         color=CYAN if hot else INK)
    text(s, x, Inches(2.95), Inches(2.2), Inches(0.4), sub, size=13, color=MUTED)
    if i < 2:
        text(s, x + Inches(2.25), Inches(2.15), Inches(0.6), Inches(0.6), "→",
             size=24, color=CYAN_D)
text(s, ML, Inches(3.55), Inches(3.4), Inches(0.4), "↺ 自举循环，一轮更快一轮",
     size=14, color=VIOLET, bold=True)
note(s, Inches(4.5), "行话叫“自举式迭代”：只用于合成数据与验证环节（9月3日技术报告）。", size=14)
note(s, Inches(5.2), [("相当于儿子不用请家教——他爹，就是清华教授。", {'color': INK, 'bold': True})], size=17)
pageno(s)

# ============ 05 快慢脑：AIME 跃迁 ============
s = slide()
kicker(s, "04 / 架构")
title(s, [("快慢脑，焊死了", {})])
hero(s, Inches(2.0), "13.4→83.3", "%", size=76)
text(s, ML + Inches(5.6), Inches(2.35), Inches(2.9), Inches(0.6), "o1 慢思考后 AIME 数学考跃迁",
     size=13, color=MUTED, anchor=MSO_ANCHOR.MIDDLE)
for i, (yr, tx, hot) in enumerate([("2024.9", "o1 学会慢思考", False), ("2025.8", "GPT-5 合体", False),
                                    ("2026.9", "GPT-6 焊死", True)]):
    x = ML + Inches(2.95) * i
    d = Inches(0.14) if hot else Inches(0.1)
    rect(s, x + Inches(0.05), Inches(4.4) - d / 2, d, d, CYAN if hot else CYAN_D)
    text(s, x + Inches(0.35), Inches(4.12), Inches(1.3), Inches(0.35), yr, size=14,
         color=CYAN if hot else MUTED, bold=hot)
    text(s, x + Inches(0.35), Inches(4.55), Inches(2.4), Inches(0.4), tx, size=13,
         color=INK if hot else MUTED)
rect(s, ML, Inches(4.4), Inches(8.3), Emu(19050), CYAN_D)
note(s, Inches(5.3), [("接下来不是缺零件，是练级了。", {'color': INK, 'bold': True, 'size': 17}),
                      ("　人脑本来就是快直觉 + 慢推理的双系统。", {'size': 13})])
pageno(s)

# ============ 06 三派：引用式 ============
s = slide()
kicker(s, "05 / 论战")
title(s, [("AGI 到没到？", {}), ("三个大神，三个立场", {'color': CYAN})])
for i, (name, quote, tag, col) in enumerate([
        ("Altman", "“几千天内出超智能。”", "OpenAI CEO · 卖铲子的", CYAN),
        ("LeCun", "“自回归 LLM 到不了 AGI。”", "图灵奖得主 · 押新赛道", VIOLET),
        ("Hinton", "“下个十年全面超越人类。”", "深度学习教父 · 在赎罪", CORAL)]):
    y = Inches(2.1 + i * 1.15)
    text(s, ML, y, Inches(1.8), Inches(0.5), name, size=22, bold=True, color=col)
    text(s, ML + Inches(2.0), y, Inches(4.6), Inches(0.5), quote, size=17, color=INK)
    text(s, ML + Inches(6.7), y + Inches(0.06), Inches(1.9), Inches(0.4), tag, size=11, color=MUTED)
    if i < 2:
        rect(s, ML, y + Inches(0.82), Inches(8.3), Emu(12700), RGBColor(0x1B, 0x24, 0x3A))
note(s, Inches(5.5), [("都别全信，但都值得听一遍。", {'color': INK, 'bold': True, 'size': 16})])
pageno(s)

# ============ 07 现实：两个大数字 ============
s = slide()
kicker(s, "06 / 现实")
title(s, [("水面没开，", {}), ("锅底已经热了", {'color': CORAL})])
hero(s, Inches(1.95), "7→4", "个月", size=88, w=Inches(4.6))
text(s, ML, Inches(3.6), Inches(4.4), Inches(0.6), "AI 可干任务时长翻倍周期（METR）",
     size=13, color=MUTED)
hero(s, Inches(1.95), "-16", "%", size=88, color=CORAL, x=Inches(5.35), w=Inches(3.9))
text(s, Inches(5.35), Inches(3.6), Inches(3.9), Inches(0.6), "22–25岁高暴露岗位招聘量（ADP）",
     size=13, color=MUTED)
note(s, Inches(4.6), "条件：高暴露、应届层，不是全员。")
note(s, Inches(5.25), [("温水煮青蛙最狠的不是水温——是温度计就在你手里，你却从来不看。",
                        {'color': INK, 'bold': True})], size=16)
pageno(s)

# ============ 08 中国：hero 3% ============
s = slide()
kicker(s, "07 / 太平洋这边")
title(s, [("别问谁有霸权——", {}), ("现在的霸权是复数", {'color': CYAN})])
hero(s, Inches(2.0), "3", "%")
text(s, ML + Inches(2.3), Inches(2.35), Inches(5.5), Inches(0.6),
     "中美顶尖模型差距（Stanford AI 指数 · 前15名中国占8席）", size=14, color=MUTED,
     anchor=MSO_ANCHOR.MIDDLE)
for i, (k, v) in enumerate([("同一周", "阿里 Qwen3-Max：万亿参数 · 开源"),
                            ("2024.12", "DeepSeek-V3：557万美元训练 671B")]):
    y = Inches(4.15 + i * 0.75)
    text(s, ML, y, Inches(1.5), Inches(0.4), k, size=12, color=CYAN)
    text(s, ML + Inches(1.7), y - Inches(0.03), Inches(6.8), Inches(0.45), v, size=16, color=INK, bold=True)
pageno(s)

# ============ 09 视角：金句页 ============
s = slide()
kicker(s, "08 / 独特视角")
text(s, Inches(0.7), Inches(2.2), Inches(8.6), Inches(1.8),
     [("AGI 不是 deadline，", {}), ("\n是海拔。", {'color': CYAN})],
     size=44, bold=True, leading=1.35, align=PP_ALIGN.CENTER)
rect(s, Inches(4.2), Inches(4.35), Inches(1.6), Emu(38100), CYAN)
text(s, Inches(0.7), Inches(4.75), Inches(8.6), Inches(0.6),
     "不是奇点式爆炸，是温水式渗透——等新闻铺天盖地那天，格局早定了。",
     size=16, color=MUTED, align=PP_ALIGN.CENTER)
text(s, Inches(0.7), Inches(5.35), Inches(8.6), Inches(0.5),
     "奇点论卖票，渗透论过日子。", size=17, color=INK, bold=True, align=PP_ALIGN.CENTER)
pageno(s)

# ============ 10 行动 + 预告 ============
s = slide()
kicker(s, "09 / 行动")
title(s, [("今天，把一件小事", {}), ("交给 AI", {'color': CYAN})])
for i, (step, detail) in enumerate([
        ("打开", "Qwen / DeepSeek / Kimi，任一免费开源模型"),
        ("丢任务", "一封邮件 · 一份总结 · 一段翻译"),
        ("长体感", "用一次，超过九成只会刷发布会的人")]):
    y = Inches(2.1 + i * 0.95)
    text(s, ML, y, Inches(0.8), Inches(0.5), f"{i+1}", size=26, bold=True, color=CYAN)
    text(s, ML + Inches(0.9), y, Inches(1.6), Inches(0.4), step, size=18, bold=True)
    text(s, ML + Inches(2.6), y + Inches(0.05), Inches(5.9), Inches(0.5), detail, size=15, color=MUTED)
rect(s, ML, Inches(5.15), Inches(1.2), Emu(38100), CYAN)
text(s, ML, Inches(5.4), CW, Inches(0.8),
     [("关注 Andy · 下期：", {'color': CYAN, 'bold': True, 'size': 14}),
      ("《一周两大王牌：Claude 5.1 对打 GPT-6》", {'size': 18, 'bold': True})], leading=1.4)
pageno(s)

OUT = "/Volumes/DATA/hermes-agent-main/mywork/ai_ep01/GPT6来了_AI演化论_EP01_4x3.pptx"
prs.save(OUT)
print("saved:", OUT, "slides:", len(prs.slides._sldIdLst))
