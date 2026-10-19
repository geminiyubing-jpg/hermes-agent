# -*- coding: utf-8 -*-
"""《钱是什么？》EP01 — 20 页 PPTX 生成器（内容：飞书逐页稿v4审批版）
设计系统：暗夜鎏金 · 16:9 · PingFang SC
"""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn

BG      = RGBColor(0x0E, 0x12, 0x20)
BG2     = RGBColor(0x15, 0x1B, 0x2E)
GOLD    = RGBColor(0xD4, 0xAF, 0x37)
GOLD_D  = RGBColor(0x8C, 0x73, 0x24)
INK     = RGBColor(0xEC, 0xE8, 0xDC)
MUTED   = RGBColor(0x9A, 0xA3, 0xB8)
RED     = RGBColor(0xC0, 0x39, 0x3B)
LINE_C  = RGBColor(0x2A, 0x33, 0x50)
FONT = "PingFang SC"
W, H = Inches(13.333), Inches(7.5)

prs = Presentation()
prs.slide_width, prs.slide_height = W, H
BLANK = prs.slide_layouts[6]
_pageno = [0]


def _ea(run, name=FONT):
    rPr = run._r.get_or_add_rPr()
    ea = rPr.find(qn('a:ea'))
    if ea is None:
        ea = rPr.makeelement(qn('a:ea'), {})
        rPr.append(ea)
    ea.set('typeface', name)


def text(slide, x, y, w, h, runs, size=18, color=INK, bold=False,
         align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, leading=1.2):
    tb = slide.shapes.add_textbox(x, y, w, h)
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
        r = p.add_run()
        r.text = txt
        f = r.font
        f.name = ov.get('font', FONT)
        f.size = Pt(ov.get('size', size))
        f.bold = ov.get('bold', bold)
        f.color.rgb = ov.get('color', color)
        _ea(r, ov.get('font', FONT))
    return tb


def shape(slide, kind, x, y, w, h, fill=None, line=None, line_w=1.0):
    sp = slide.shapes.add_shape(kind, x, y, w, h)
    if fill is None:
        sp.fill.background()
    else:
        sp.fill.solid()
        sp.fill.fore_color.rgb = fill
    if line is None:
        sp.line.fill.background()
    else:
        sp.line.color.rgb = line
        sp.line.width = Pt(line_w)
    sp.shadow.inherit = False
    if kind == MSO_SHAPE.ROUNDED_RECTANGLE:
        try:
            sp.adjustments[0] = 0.075
        except Exception:
            pass
    return sp


def new_slide():
    s = prs.slides.add_slide(BLANK)
    shape(s, MSO_SHAPE.RECTANGLE, 0, 0, W, H, fill=BG)
    _pageno[0] += 1
    return s


def kicker(s, txt):
    text(s, Inches(0.9), Inches(0.5), Inches(9), Inches(0.4), txt, size=13, color=GOLD, bold=True)
    shape(s, MSO_SHAPE.RECTANGLE, Inches(0.9), Inches(0.92), Inches(0.6), Emu(28575), fill=GOLD)


def head(s, runs):
    text(s, Inches(0.9), Inches(1.18), Inches(11.6), Inches(1.0), runs, size=30, bold=True, leading=1.25)


def page_no(s):
    text(s, Inches(12.35), Inches(6.95), Inches(0.7), Inches(0.35),
         f"{_pageno[0]:02d}", size=12, color=MUTED, align=PP_ALIGN.RIGHT)


def card(s, x, y, w, h, lab, title, body, accent=GOLD, tsize=17, bsize=12):
    shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h, fill=BG2, line=LINE_C)
    shape(s, MSO_SHAPE.RECTANGLE, x + Inches(0.4), y + Inches(0.35), Inches(0.28), Emu(38100), fill=accent)
    ty = y + Inches(0.28)
    if lab:
        text(s, x + Inches(0.32), ty, w - Inches(0.64), Inches(0.3), lab, size=11, color=MUTED)
        ty += Inches(0.42)
    text(s, x + Inches(0.32), ty, w - Inches(0.64), Inches(0.42), title, size=tsize, color=accent if accent != INK else INK, bold=True)
    text(s, x + Inches(0.32), ty + Inches(0.62), w - Inches(0.64), h - (ty - y) - Inches(0.85), body,
         size=bsize, color=MUTED, leading=1.35)


def cardrow(s, items, y=Inches(2.9), h=Inches(3.4), gap=Inches(0.35), x0=Inches(0.9)):
    n = len(items)
    w = (Inches(11.55) - gap * (n - 1)) / n
    for i, it in enumerate(items):
        lab, t, b = it[0], it[1], it[2]
        acc = it[3] if len(it) > 3 else GOLD
        card(s, x0 + (w + gap) * i, y, w, h, lab, t, b, accent=acc)
    return w


def timeline(s, x, y, w, items, highlight=None):
    shape(s, MSO_SHAPE.RECTANGLE, x, y + Inches(1.15), w, Emu(19050), fill=GOLD_D)
    n = len(items)
    for i, (yr, tx) in enumerate(items):
        cx = x + Emu(int(w / (n - 1))) * i if n > 1 else x
        hot = (highlight == i)
        d = Inches(0.16) if hot else Inches(0.12)
        shape(s, MSO_SHAPE.OVAL, cx - d / 2, y + Inches(1.15) - d / 2 + Emu(9525), d, d,
              fill=GOLD if hot else GOLD_D)
        text(s, cx - Inches(0.9), y - Inches(0.05), Inches(1.8), Inches(0.4), yr,
             size=15, color=GOLD if hot else MUTED, bold=hot, align=PP_ALIGN.CENTER)
        text(s, cx - Inches(1.0), y + Inches(1.45), Inches(2.0), Inches(1.1), tx,
             size=11, color=INK if hot else MUTED, align=PP_ALIGN.CENTER, leading=1.3)


def coin(s, cx, cy, d_out=Inches(4.0), label=None):
    shape(s, MSO_SHAPE.OVAL, cx, cy, d_out, d_out, fill=None, line=GOLD_D, line_w=1.0)
    shape(s, MSO_SHAPE.OVAL, cx + d_out / 8, cy + d_out / 8, d_out * 0.75, d_out * 0.75,
          fill=None, line=GOLD_D, line_w=0.75)
    shape(s, MSO_SHAPE.OVAL, cx + d_out / 4, cy + d_out / 4, d_out * 0.5, d_out * 0.5,
          fill=None, line=GOLD, line_w=1.5)
    hole = d_out * 0.24
    sq = shape(s, MSO_SHAPE.RECTANGLE, cx + d_out / 2 - hole / 2, cy + d_out / 2 - hole / 2,
               hole, hole, fill=BG, line=GOLD, line_w=1.8)
    sq.rotation = 45
    if label:
        text(s, cx, cy + d_out / 2 - Inches(1.1), d_out, Inches(0.6), label, size=22,
             color=GOLD, bold=True, align=PP_ALIGN.CENTER)


def bullets(s, x, y, w, items, gap=Inches(0.72), tsize=15, bsize=12):
    for i, (t, b) in enumerate(items):
        shape(s, MSO_SHAPE.RECTANGLE, x + Inches(0.05), y + gap * i + Inches(0.12),
              Inches(0.24), Emu(28575), fill=GOLD)
        text(s, x + Inches(0.55), y + gap * i, w - Inches(0.55), Inches(0.4), t,
             size=tsize, color=INK, bold=True)
        text(s, x + Inches(0.55), y + gap * i + Inches(0.4), w - Inches(0.55), Inches(0.5), b,
             size=bsize, color=MUTED, leading=1.3)


def bigstat(s, x, y, num, unit, label, size=96, color=GOLD, w=Inches(6.5)):
    text(s, x, y, w, Inches(1.6), [(num, {'size': size, 'color': color, 'bold': True}),
                                   (" " + unit, {'size': 24, 'color': color})],
         anchor=MSO_ANCHOR.MIDDLE)
    text(s, x + Inches(0.1), y + Inches(1.7), w - Inches(0.2), Inches(0.8), label,
         size=14, color=MUTED, leading=1.35)


def closing(s, quote):
    shape(s, MSO_SHAPE.RECTANGLE, Inches(0.9), Inches(6.35), Inches(1.1), Emu(38100), fill=RED)
    text(s, Inches(0.9), Inches(6.6), Inches(11.6), Inches(0.6), quote, size=15, color=INK)


# ============ 01 封面 ============
s = new_slide()
coin(s, Inches(8.6), Inches(1.4), Inches(4.6))
text(s, Inches(0.9), Inches(1.8), Inches(8), Inches(0.5), "王朝的钱袋子 · 第一期",
     size=16, color=GOLD, bold=True)
text(s, Inches(0.85), Inches(2.35), Inches(8.5), Inches(1.5), "钱是什么？", size=60, color=INK, bold=True)
shape(s, MSO_SHAPE.RECTANGLE, Inches(0.92), Inches(3.75), Inches(1.4), Emu(38100), fill=GOLD)
text(s, Inches(0.9), Inches(4.05), Inches(7.8), Inches(1.2),
     [("天天见面的问题，人类想了五千年", {})], size=20, color=MUTED)
text(s, Inches(0.9), Inches(5.0), Inches(7.8), Inches(1.6),
     "从债务与账本的起源，到中国的贝壳铜钱银锭，\n再到无锚的美元与数字货币——一条脉络，讲透两个字。",
     size=14, color=MUTED, leading=1.6)
text(s, Inches(0.9), Inches(6.85), Inches(6), Inches(0.4), "全片 25 分钟 · 20 页", size=11, color=MUTED)

# ============ 02 为什么会产生货币(上) ============
s = new_slide()
kicker(s, "01 / 起源")
head(s, [("教科书说错了：", {}), ("“以物易物”从未被找到", {'color': GOLD})])
bx, by, bs = Inches(0.9), Inches(2.5), Inches(4.6)
text(s, bx, by, bs, Inches(1.2), "以物易物", size=54, color=INK, bold=True, align=PP_ALIGN.CENTER)
text(s, bx, by + Inches(1.3), bs, Inches(0.5),
     "人类学家找了 100 多年，一个都没找到", size=13, color=MUTED, align=PP_ALIGN.CENTER)
x1, x2 = bx + Inches(0.3), bx + bs - Inches(0.3)
shape(s, MSO_SHAPE.RECTANGLE, x1, by + Inches(0.15), x2 - x1, Emu(47625), fill=RED, line=None)
sp = shape(s, MSO_SHAPE.RECTANGLE, x1, by + Inches(0.15), x2 - x1, Emu(47625), fill=RED)
sp.rotation = 12
sp2 = shape(s, MSO_SHAPE.RECTANGLE, x1, by + Inches(0.15), x2 - x1, Emu(47625), fill=RED)
sp2.rotation = -12
bullets(s, Inches(6.2), Inches(2.45), Inches(6.2), [
    ("亚当·斯密的故事", "“我用羊换你的米”→需求双重巧合→发明货币。听着合理，但只是思想实验。"),
    ("人类学界的检索结果", "格雷伯《债》开篇论断：记录在案的部落社会，无一例以物易物经济的确凿证据。"),
    ("考古挖到的是账本", "五千年前美索不达米亚泥板，记的是“谁欠神庙三谢克尔大麦”。人类最早的文字就是账本。"),
    ("结论", "账本比钱古老，债务比硬币古老。钱不是为方便交易发明——钱从记账里长出来。"),
], gap=Inches(1.02), bsize=11.5)
page_no(s)

# ============ 03 为什么会产生货币(下) ============
s = new_slide()
kicker(s, "01 / 起源")
head(s, [("雅浦岛巨石：石头不动，", {}), ("“账”在人们口中传递", {'color': GOLD})])
cardrow(s, [
    ("太平洋 · 雅浦岛", "石头就是钱",
     "石币大者直径四米、重四吨。交易时石头原地不动，全村口头见证：“这块石头的主人换了。”", GOLD),
    ("沉海的石头", "照样流通",
     "有一块石头沉进海底，没人见过——全村账本上它还在，就照样流通、照样值钱。", INK),
    ("弗里德曼之问", "和美联储有区别吗？",
     "德国殖民政府在石头上画记号宣布罚没，岛民立刻变穷。货币宗师问：美联储金库抽屉上的记号，与石记何异？", RED),
], y=Inches(2.6), h=Inches(3.3))
closing(s, "钱不是那个东西——钱是全社会共同维护的一本账：谁欠谁多少。")
page_no(s)

# ============ 04 三大职能 ============
s = new_slide()
kicker(s, "02 / 职能")
head(s, [("三大职能，", {}), ("一个本质", {'color': GOLD})])
cardrow(s, [
    ("职能一", "交易媒介", "上班拿工资、超市买东西，不用扛半头猪——钱是最高效的中介。"),
    ("职能二", "计价单位", "猪肉三十一斤、房子三万一平——所有价值用同一把尺子量。少了他，经济当场瘫痪。"),
    ("职能三", "价值储藏", "今天的劳动换成钱存起来，十年后再花。你存的不是纸，是“社会欠你”的记账凭证。"),
], y=Inches(2.55), h=Inches(2.9))
shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.9), Inches(5.75), Inches(11.55), Inches(0.95),
      fill=BG2, line=GOLD, line_w=1.4)
text(s, Inches(0.9), Inches(5.95), Inches(11.55), Inches(0.6),
     [("职能是表象，", {}), ("账本是本体", {'color': GOLD, 'bold': True, 'size': 18}),
      ("——记住这句话，后面五千年，全部通吃。", {})],
     size=16, color=INK, align=PP_ALIGN.CENTER)
page_no(s)

# ============ 05 什么东西当货币 ============
s = new_slide()
kicker(s, "03 / 材料")
head(s, [("稀缺来自远方，", {}), ("价值来自共识", {'color': GOLD})])
text(s, Inches(0.9), Inches(2.15), Inches(11.5), Inches(0.5),
     "答案高度一致：稀缺、可分、耐用、共识。中国人选了贝壳——来自遥远的南海，中原得不到。",
     size=14, color=MUTED)
# 进化链
evo = ["贝壳", "铜贝", "布币", "刀币", "圜钱", "秦半两"]
ex, ey, ew, eg = Inches(0.9), Inches(3.0), Inches(1.7), Inches(0.28)
for i, e in enumerate(evo):
    shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, ex + (ew + eg) * i, ey, ew, Inches(0.85),
          fill=BG2, line=GOLD if i in (0, 5) else LINE_C)
    text(s, ex + (ew + eg) * i, ey + Inches(0.2), ew, Inches(0.5), e,
         size=17, color=GOLD if i in (0, 5) else INK, bold=True, align=PP_ALIGN.CENTER)
    if i < len(evo) - 1:
        text(s, ex + (ew + eg) * i + ew, ey + Inches(0.18), eg, Inches(0.5), "→",
             size=16, color=GOLD_D, align=PP_ALIGN.CENTER)
bullets(s, Inches(0.9), Inches(4.25), Inches(5.6), [
    ("汉字是货币史的化石", "财、货、贵、贱、购、贸——全是贝字旁。三千二百年前妇好墓陪葬六千枚海贝。"),
    ("春秋战国四大体系", "韩赵魏布币（铲）、齐燕刀币（刀）、秦圜钱（圆孔）、楚蚁鼻钱与金版郢爰。"),
], gap=Inches(1.05), bsize=11.5)
card(s, Inches(7.05), Inches(4.25), Inches(5.4), Inches(2.2), None,
     "四五种钱并存的乱局",
     "跨个国就得换汇，比价表排到眼花。这个乱局，等着一个人来终结——下一页，秦始皇。", accent=RED, tsize=16, bsize=12.5)
page_no(s)

# ============ 06 秦汉 ============
s = new_slide()
kicker(s, "04 / 中国史 · 一")
head(s, [("秦汉：", {}), ("统一的账本", {'color': GOLD})])
coin(s, Inches(0.95), Inches(2.6), Inches(3.3), label="半两")
text(s, Inches(0.9), Inches(6.1), Inches(3.5), Inches(0.6),
     "方孔圆钱两千年，天圆地方", size=12, color=MUTED, align=PP_ALIGN.CENTER)
bullets(s, Inches(5.0), Inches(2.45), Inches(7.4), [
    ("前221 · 秦半两", "秦始皇统一六国，顺带统一货币。圆形方孔从此定型，此后两千年未变。"),
    ("汉初 · 九次改币", "越改越乱，私铸成风——因私铸被处死者数十万，法不责众，官府杀不过来。"),
    ("前118 · 五铢钱", "汉武帝出手：铸币权收归中央，重量成色统一。这一铸就是七百年，中国流通最久的货币。"),
    ("五铢做对了什么", "三个字：不折腾。轻重合适、成色足、政府垄断——信用稳定，账本可信。"),
], gap=Inches(1.0), bsize=11.5)
closing(s, "货币的生命，就是信用的生命。")
page_no(s)

# ============ 07 唐宋 ============
s = new_slide()
kicker(s, "04 / 中国史 · 二")
head(s, [("唐宋：从“重量”到", {}), ("“信用”", {'color': GOLD})])
coin(s, Inches(0.95), Inches(2.7), Inches(3.1), label="通寶")
text(s, Inches(0.9), Inches(6.0), Inches(3.3), Inches(0.5), "钱开始从“东西”变成“符号”",
     size=12, color=MUTED, align=PP_ALIGN.CENTER)
bullets(s, Inches(5.0), Inches(2.35), Inches(7.4), [
    ("621 · 开元通宝", "“通宝”＝通行的宝货。以前的钱叫半两、五铢，都是重量；从此钱有了自己的名字。体系沿用近一千三百年。"),
    ("北宋 · 交子诞生", "四川用铁钱，买一匹布要背上百斤。成都十六家富商发行存钱凭证——交子。"),
    ("1023 · 收归官办", "朝廷设益州交子务：世界第一张政府纸币，比欧洲早六百多年。首届发行126万贯。"),
    ("准备金率 28%", "纸能买东西，不是纸值钱——是发行者的信用。钱第一次彻底脱离“内在价值”。"),
], gap=Inches(1.0), bsize=11.5)
closing(s, "宋朝人的这场实验，比全世界早了六百年。")
page_no(s)

# ============ 08 元明清 ============
s = new_slide()
kicker(s, "04 / 中国史 · 三")
head(s, [("元明清：", {}), ("纸与银的两极", {'color': GOLD})])
cardrow(s, [
    ("元 · 明", "宝钞：纸的崩盘", "没有准备金硬发，越印越毛，形同废纸，朝廷自己都不收。教训：没有纪律的信用，比没有信用更糟。", RED),
    ("1557–1640s", "白银：银的流入", "隆庆开关后，美洲日本白银涌入——学界估算全球约三分之一白银流入中国。1581年一条鞭法：所有税收折银。", INK),
    ("1630s", "银竭则国亡", "中国自己不产银。美洲减产、日本锁国，白银流入骤降——明朝立刻通缩加财政枯竭。", GOLD),
], y=Inches(2.6), h=Inches(3.3))
closing(s, "用别人家的钱当自家的锚，是把命脉交到别人手里——四百年后，有个大国会再体会一次。")
page_no(s)

# ============ 09 铸币权之战 ============
s = new_slide()
kicker(s, "05 / 发行权")
head(s, [("钱是谁造的？——", {}), ("记账权之战，吵了两千年", {'color': GOLD})])
timeline(s, Inches(1.0), Inches(2.7), Inches(11.3), [
    ("上古", "人人私铸\n贝壳谁捡归谁\n铜钱民间也铸"),
    ("前118", "汉武帝收权\n上林三官专铸\n私铸者死"),
    ("宋 元 明", "朝廷印纸\n超发→贬值→崩盘\n同一剧本反复"),
], highlight=1)
card(s, Inches(0.9), Inches(5.0), Inches(11.55), Inches(1.5), None,
     "发行权的悖论",
     "集中解决了“乱”，却制造了“滥”。货币的质量从此取决于发行者的自律——而自律，是世界上最不可靠的东西。这就要等一种新的机构出场。",
     accent=RED, tsize=16, bsize=13)
page_no(s)

# ============ 10 两派吵架 ============
s = new_slide()
kicker(s, "06 / 货币理论")
head(s, [("钱是什么？两派", {}), ("吵架两百年", {'color': GOLD})])
cwx = Inches(5.6)
card(s, Inches(0.9), Inches(2.6), cwx, Inches(3.2), "左翼 · 金本位时代主流",
     "金属主义：钱＝金银",
     "钱必须真金白银，本身有价值，纸币只是仓库凭条——理论上随时能去银行换黄金。")
card(s, Inches(0.9) + cwx + Inches(0.35), Inches(2.6), cwx, Inches(3.2), "右翼 · 克纳普（德国）",
     "名目主义：钱＝国家的字",
     "钱的价值来自国家权力与法令，不需金属背书。诞生在货币混乱的德意志——“国家说了算”的渴望。", accent=INK)
text(s, Inches(6.35), Inches(4.0), Inches(0.7), Inches(0.6), "VS", size=24, color=GOLD,
     bold=True, align=PP_ALIGN.CENTER)
closing(s, "1971年终审：货币与黄金脱钩，金属主义退场。但各对一半——钱靠国家信用，国家信用必须有约束。")
page_no(s)

# ============ 11 央行诞生 ============
s = new_slide()
kicker(s, "07 / 近现代")
head(s, [("央行的诞生：", {}), ("发钱的机器变了", {'color': GOLD})])
timeline(s, Inches(1.0), Inches(2.35), Inches(11.3), [
    ("1668", "瑞典央行\n（最早雏形）"),
    ("1694", "英格兰银行\n商人借国王120万英镑\n换来发钞特权"),
    ("1913", "美联储成立",),
    ("1948", "人民币诞生\n石家庄 · 第一套"),
], highlight=1)
card(s, Inches(0.9), Inches(4.6), Inches(11.55), Inches(1.9), None,
     "现代货币的本质：钱是“记”出来的",
     "你在银行贷款三百万——银行账上左边记“你欠我”，右边记“我欠你”——三百万就诞生了。英格兰银行2014年论文白纸黑字：货币是贷款创造的。\n现代的钱，是键盘敲出来的。",
     accent=GOLD, tsize=17, bsize=13)
page_no(s)

# ============ 12 黄金锚 ============
s = new_slide()
kicker(s, "08 / 有锚 → 无锚 · 一")
head(s, [("黄金锚时代：", {}), ("锚是纪律，也是枷锁", {'color': GOLD})])
bigstat(s, Inches(0.9), Inches(2.5), "35", "美元 = 1盎司黄金",
       "1944年布雷顿森林：44国定规矩——美元挂钩黄金，各国货币挂钩美元。全世界的钱，都拴在金库里。")
bullets(s, Inches(7.3), Inches(2.45), Inches(5.1), [
    ("锚的好处：纪律", "想发钱先看金库。印多了人家来换黄金，换不出就破产——锁链拴住乱花钱的手。"),
    ("锚的致命伤：不够用", "世界经济爆炸增长，黄金跟不上→钱不够→通缩。大萧条之惨，正因金本位捆住了央行救市的手。"),
    ("结论", "世界经济要增长，就需要能伸缩的锁链。于是人类做了一个大实验：把锚扔了。"),
], gap=Inches(1.28), bsize=11.5)
page_no(s)

# ============ 13 1971 扔锚之夜 ============
s = new_slide()
kicker(s, "08 / 有锚 → 无锚 · 二")
head(s, [("1971.8.15：", {}), ("扔锚之夜", {'color': RED})])
bigstat(s, Inches(0.9), Inches(2.4), "98%", "购买力缩水",
       "1971年35美元一盎司的黄金，今天5000多美元。以黄金计，美元购买力53年缩水超98%——无锚时代最长的一堂通胀课。",
       color=RED)
bullets(s, Inches(7.3), Inches(2.45), Inches(5.1), [
    ("戴维营密会", "8月13日尼克松带15个心腹关门两天；15日周日市场休市——时间精心挑选。"),
    ("为什么掀桌子", "美国印的美元远超诺克斯堡的黄金；法国带头一船船运美元换金。再换，金库要空。"),
    ("实验开始", "1973年各国货币全面浮动。美元从“黄金的欠条”变成“美联储的欠条”——人类首次活在无锚世界。"),
], gap=Inches(1.28), bsize=11.5)
page_no(s)

# ============ 14 美元四柱 ============
s = new_slide()
kicker(s, "09 / 美元信用")
head(s, [("无锚大厦的", {}), ("四根柱子", {'color': GOLD})])
cardrow(s, [
    ("柱一", "贸易结算网络", "全球大宗商品、石油多半以美元计价——想买石油先换美元。用的人越多越离不开：网络的暴力。"),
    ("柱二", "美债循环", "各国赚了美元回头买美债，钱又流回美国。美债规模超36万亿美元——全世界最大的蓄水池。"),
    ("柱三", "SWIFT清算", "全球跨境清算主干道。2022年俄银行被踢出、3000亿储备被冻结——清算通道本身就是武器。", RED),
    ("柱四", "美国国力", "军事、科技、法治、全球最大消费市场。"),
], y=Inches(2.6), h=Inches(3.0))
closing(s, "柱子都是人造的，会风化：各国央行连续四年净购黄金，外储黄金占比17%→27%。大厦还稳，住的人已在买保险。")
page_no(s)

# ============ 15 三次压力测试 ============
s = new_slide()
kicker(s, "10 / 压力测试")
head(s, [("无锚大厦稳不稳？", {}), ("三次测试：都晃，都没塌", {'color': GOLD})])
cardrow(s, [
    ("1997", "亚洲金融危机", "泰铢腰斩、韩国全民捐金。IMF入场，三年缓过来——晃了，没塌。"),
    ("2008", "雷曼倒闭", "全球心脏骤停，无锚时代第一次系统性危机。央行联手注资，半年止血，没重演1929。"),
    ("2023", "硅谷银行", "48小时被挤兑倒闭——手机银行时代挤兑速度史上第一。财政部连夜全额兜底。"),
], y=Inches(2.6), h=Inches(2.7))
card(s, Inches(0.9), Inches(5.55), Inches(11.55), Inches(1.3), None,
     "终极保命设计",
     "央行理论上可无限供应流动性：金本位黄金不够就是不够，无锚时代键盘管够——挤兑在数学上可被终结。但每次危机都靠放水，全球债务已超300万亿美元。短期稳，长期没人知道。",
     accent=GOLD, tsize=16, bsize=12.5)
page_no(s)

# ============ 16 衍生品金字塔 ============
s = new_slide()
kicker(s, "11 / 衍生演化")
head(s, [("从钱到衍生品：", {}), ("倒立的金字塔", {'color': GOLD})])
layers = [
    ("衍生品：期货/期权/互换——对“未来的钱”的合约", GOLD, Inches(0.9)),
    ("债券 · 股票 · 理财——对钱的种种索取权", INK, Inches(1.3)),
    ("银行存款——放贷创造的存款货币（比底层大数倍）", INK, Inches(1.7)),
    ("基础货币——央行发行", INK, Inches(2.1)),
]
ly = Inches(2.55)
for name, acc, wid in layers:
    x = Inches(6.75) - wid / 2
    shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, x, ly, wid, Inches(0.72), fill=BG2,
          line=GOLD if acc == GOLD else LINE_C)
    text(s, x, ly + Inches(0.2), wid, Inches(0.4), name, size=12.5,
         color=GOLD if acc == GOLD else MUTED, align=PP_ALIGN.CENTER)
    ly += Inches(0.88)
bigstat(s, Inches(9.6), Inches(2.7), "699.5", "万亿美元",
       "BIS 2024年末口径：全球场外衍生品名义本金，约为全球年GDP的6倍。", size=72, w=Inches(3.2))
text(s, Inches(0.9), Inches(6.3), Inches(8.5), Inches(0.6),
     [("钱从交易媒介，繁衍出比实体经济大六倍的影子世界。", {'color': INK, 'bold': True})],
     size=15)
page_no(s)

# ============ 17 数字货币一 ============
s = new_slide()
kicker(s, "12 / 数字货币 · 一")
head(s, [("国家队的进场：", {}), ("没有新钱，只有新形态", {'color': GOLD})])
cwx2 = Inches(5.6)
card(s, Inches(0.9), Inches(2.6), cwx2, Inches(3.2), "国家队",
     "数字人民币 2.0",
     "今年1月1日正式运行：钱包计息、纳入存款准备金、受存款保险保障——从“数字现金”升级为“数字存款”。134个国家在探索央行数字货币。")
card(s, Inches(0.9) + cwx2 + Inches(0.35), Inches(2.6), cwx2, Inches(3.2), "市场队",
     "持牌稳定币",
     "香港《稳定币条例》生效，高门槛发牌；美国GENIUS法案：1:1储备、月度披露、持牌发行——私人数字欠条被装进监管笼子。", accent=INK)
closing(s, "数字人民币是央行欠条换了形态，持牌稳定币是私人欠条戴上镣铐。记账权的争夺还在，只是换了战场。")
page_no(s)

# ============ 18 比特币 ============
s = new_slide()
kicker(s, "12 / 数字货币 · 二")
head(s, [("比特币：", {}), ("最彻底的实验", {'color': GOLD})])
text(s, Inches(0.9), Inches(2.1), Inches(11.5), Inches(0.5),
     "革命性：总量2100万枚写死代码，无央行能超发、无政府能冻结。哈耶克“货币非国家化”的数字实践。但用四根柱子检验——",
     size=13.5, color=MUTED)
pillars = [
    ("征税权", "无", "没有任何场景强制你用它，接受度全靠信仰。", RED),
    ("资产锚", "无", "价值完全靠交易价格撑着：值多少，取决于下一个买家出多少。", RED),
    ("制度兜底", "无", "私钥丢了币就永远没了——估算数百万枚已无法动用。没有客服，没有挂失。", RED),
    ("财富分配", "失衡", "极少数早期者握海量筹码，后来者高位接盘——更像财富再分配游戏。", RED),
]
cardrow(s, [(f"柱{i+1}", t, b, acc) for i, (t, _, b, acc) in enumerate(pillars)],
        y=Inches(3.0), h=Inches(2.7))
closing(s, "它只有“共识”一根柱子。缺柱子的实验，终究是实验——正规发行的数字货币，才是未来。")
page_no(s)

# ============ 19 总结 ============
s = new_slide()
kicker(s, "13 / 总结")
head(s, [("五千年，一条主线：", {}), ("变的是形式，不变的是账本", {'color': GOLD})])
timeline(s, Inches(0.9), Inches(2.4), Inches(11.5), [
    ("贝壳", "稀缺天然物\n共识的起点"),
    ("铜钱", "国家铸造\n信用有了形状"),
    ("纸币", "交子→法币\n发行者信用"),
    ("美元", "无锚信用\n四柱大厦"),
    ("衍生品", "自我繁殖\n影子金字塔"),
    ("数字货币", "正规军进场\n实验者退场"),
])
qa = [("从哪来？", "从债务与账本来——最早的文字是记账。"),
      ("谁来发？", "从私铸到国家垄断到央行——每次转移都是权力重塑。"),
      ("怎么认识？", "从“钱是铜”到“国家的字”到“央行的欠条”——每深化一层，抽象一层。")]
bullets(s, Inches(0.9), Inches(4.75), Inches(11.4), qa, gap=Inches(0.62), tsize=14, bsize=12)
closing(s, "钱越来越不像“东西”，越来越像“关系”——信任在，纸是金；信任亡，金也是纸。")
page_no(s)

# ============ 20 收尾 ============
s = new_slide()
coin(s, Inches(8.9), Inches(4.0), Inches(4.2))
shape(s, MSO_SHAPE.RECTANGLE, Inches(0.9), Inches(2.2), Inches(1.15), Inches(1.15), fill=RED)
text(s, Inches(0.9), Inches(2.45), Inches(1.15), Inches(0.7), "钱", size=30, color=INK,
     bold=True, align=PP_ALIGN.CENTER)
text(s, Inches(2.4), Inches(2.2), Inches(9.5), Inches(1.4),
     "既然钱是社会账本，\n洗钱，就是往这本账里造假账。",
     size=26, bold=True, leading=1.5)
text(s, Inches(0.9), Inches(4.2), Inches(7.5), Inches(0.8),
     "五千年货币史，一半是造账的历史，一半是查账的历史。",
     size=15, color=MUTED, leading=1.5)
shape(s, MSO_SHAPE.RECTANGLE, Inches(0.9), Inches(5.6), Inches(1.1), Emu(38100), fill=GOLD)
text(s, Inches(0.9), Inches(5.85), Inches(8), Inches(1.0),
     [("下一期 · 王朝的钱袋子 第二期", {'color': GOLD, 'bold': True, 'size': 14}),
      ("\n汉武帝的破产危机——桑弘羊、盐铁专营，吵了两千年", {'size': 18, 'bold': True})],
     leading=1.5)
page_no(s)

OUT = "/Volumes/DATA/hermes-agent-main/mywork/money_pptx/钱是什么_王朝的钱袋子_EP01.pptx"
prs.save(OUT)
print("saved:", OUT, "slides:", len(prs.slides._sldIdLst))
