#!/usr/bin/env python3
"""paper-anim-video 自动作者化：PPT shape 文字 → 13页卡片布局 + 配音块→追光自动映射
用法: python3 auto_author.py --dir 工程目录 --slides /path/epX_v2/slides-html --name "GPT-2"
输入工程需先跑 build_project（有 tim_data.json + 骨架 html）。
布局策略：每页 = 标题栏 + 2列卡片网格（PPT 逐 shape 文字合并成 6-9 张卡）；
追光：每个配音块按 2-gram 重合度选中卡片，生成精确正则。
"""
import argparse, json, re, os, glob, html as htmlmod

def slide_texts(f):
    h=open(f).read()
    ts=re.findall(r'class="shape txt[^"]*" style="[^"]*">([^<]*)<',h)
    return [htmlmod.unescape(t).strip() for t in ts if t.strip()]

def grams(s,n=2):
    s=re.sub(r'[^\w一-鿿]','',s)
    return {s[i:i+n] for i in range(max(0,len(s)-n+1))} if len(s)>1 else {s}

def build_cards(texts):
    """shape文字 → 卡片列表: [{title, body}]。首条=页标题, 次条(含'·'短横)跳过页脚。"""
    title=texts[0] if texts else ''
    body=[t for t in texts[1:] if not re.match(r'^[^·]{2,30}·[^·]{2,30}$',t) and t!=title and not re.fullmatch(r'\d+\s*/\s*\d+',t)]
    # 合并成卡：短句(≤14字)作卡题吸收后续长句；孤立长句自立为卡
    cards=[]
    for t in body:
        if len(t)<=16 and not cards:
            cards.append({'title':t,'body':''}); continue
        if len(t)<=16 and cards and not cards[-1]['body'] and len(cards[-1]['title'])<=16:
            # 连续短句 → 各自成卡
            cards.append({'title':t,'body':''}); continue
        if cards and not cards[-1]['body'] and len(cards[-1]['title'])<=20:
            cards[-1]['body']=t
        else:
            cards.append({'title':re.sub(r'[：:].*$','',t)[:20] or t[:20],'body':t if len(t)>20 else ''})
    # 上限 10 卡（多了并尾）
    while len(cards)>14:
        last=cards.pop(); cards[-1]['body']=(cards[-1]['body']+' '+last['title']+' '+last['body']).strip()
    return title,cards

def layout(n):
    if n<=3: return 1,n,640
    if n<=6: return 2,3,420
    if n<=8: return 2,4,330
    if n<=12: return 3,4,260
    return 4,4,215

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--dir',required=True); ap.add_argument('--slides',required=True)
    ap.add_argument('--name',required=True)
    a=ap.parse_args()
    D=a.dir
    slides=sorted(glob.glob(f"{a.slides}/slide-*.html"))
    tim=json.load(open(f"{D}/tim_data.json"))
    while len(slides)<len(tim): slides.append(slides[-1])   # PPT 页数少于稿段时尾页复用
    ns={}; exec(open(f"{D}/project_config.py").read(),ns); durs=ns["PAGES"]

    # ---------- 生成 CSS + HTML + JS ----------
    css=[]; scenes=[]; jsfn=[]; spot={}
    vkeys=sorted(tim.keys())            # 实际页键（P01.. 或 P00..，页数可变）
    N=len(vkeys)
    for pi in range(N):
        pid=f"p{pi:02d}"; vpid=vkeys[pi]
        title,cards=build_cards(slide_texts(slides[pi]))
        rows,cols,ch=layout(len(cards))
        fs=34 if len(cards)<=4 else (26 if len(cards)<=8 else 21)
        tfs=24 if len(cards)<=4 else (20 if len(cards)<=8 else 17)
        css.append(f"""#g{pid} {{ position:absolute; left:0; right:0; top:200px; display:grid;
  grid-template-columns:repeat({cols},1fr); gap:22px; padding:0 90px; }}
#g{pid} .ac {{ min-height:{ch}px; padding:24px 26px; opacity:0; }}
#g{pid} .ac h4 {{ font-size:{tfs}px; margin-bottom:8px; }}
#g{pid} .ac p {{ font-size:{fs-8}px; color:rgba(205,220,248,.88); line-height:1.55; }}""")
        cards_html=""
        for ci,c in enumerate(cards):
            body=f"<p>{c['body']}</p>" if c['body'] else ''
            cards_html+=f'<div class="ac card auto-{ci}"><h4>{c["title"]}</h4>{body}</div>\n'
        sub=re.search(r'[：:](.*)$',title)
        scenes.append(f"""  <div class="scene" id="{pid}">
    <div class="h">{re.sub(r'[：:].*$','',title)}{('<span class="sub">'+sub.group(1)+'</span>') if sub else ''}</div>
    <div id="g{pid}">
{cards_html}    </div>
  </div>""")
        pass
        # 追光：配音块 → 2-gram 重合度最高卡片
        rules=[]
        cardgrams=[grams(c['title']+c['body']) for c in cards]
        for b in tim[vpid]:
            bg=grams(b['text'])
            best=max(range(len(cards)),key=lambda i:len(bg&cardgrams[i]))
            pat=re.escape(b['text'][:10])
            rules.append([pat,f"#g{pid} .auto-{best}"])
        spot[vpid]=rules
    jsfn=[f"function r{pi:02d}(t){{\n  document.querySelectorAll('#gp{pi:02d} .ac').forEach((el,i)=>{{\n    const e=easeOut(seg(t,.3+i*.35,1.0+i*.35)); el.style.opacity=e; }});\n}}" for pi in range(N)]

    # ---------- 注入骨架 ----------
    H=f"{D}/bert_anim.html"; s=open(H).read()
    s=re.sub(r"const PAGES=\[.*?\];", "const PAGES=["+",".join(f"['{vkeys[i]}',r{i:02d},{durs[i]:.2f}]" for i in range(N))+"];", s, flags=re.S)
    # 替换 P01-P12 场景与渲染函数（锚点：scene p01 起 → script 前 / r01 → 调度前）
    import re as _rx
    m=_rx.search(r'[ \t]*(?:<!--[^>]*-->\s*)*<div class="scene" id="p01"',s)
    a1=m.start()
    b1=s.index('\n</div>\n<script src="tim.js">')
    scenes_html="\n".join(scenes[1:])
    s=s[:a1]+"  <!-- 自动生成页 P01-P12 -->\n"+scenes_html+s[b1:]
    a2=s.index('function r01(t){'); a2=s.rindex('\n',0,a2)+1
    b2=s.index('/* ---------- 调度')
    s=s[:a2]+"\n".join(jsfn[1:])+"\n"+s[b2:]
    # CSS 替换（P01 css 起到 </style>）
    m2=_rx.search(r'/\* P01[\s\S]*?</style>',s)
    assert m2, "CSS锚点缺失"
    s=s[:m2.start()]+"/* P01-P12 自动版式 */\n"+"\n".join(css[1:])+"\n</style>"+s[m2.end():]
    # 篇名
    s=re.sub(r"<title>[^<]*</title>", f"<title>{a.name} 深度解读</title>", s)
    s=s.replace("BERT 深度解读 · <b>", f"{a.name} 深度解读 · <b>")
    s=re.sub(r'<div class="brand">[^<]*</div>', f'<div class="brand">{a.name} · 论文动态解读</div>', s)
    # P00 封面卡：用 slide-01 的统计徽章
    t0,extra=build_cards(slide_texts(slides[0]))
    stats=re.findall(r'(\d[\d./]*[MB%+]?)\s*([^|]{4,18})', ' | '.join(slide_texts(slides[0])[:14]))
    st_html="".join(f'<div class="st"><div class="v">{v.strip()}</div><div class="k">{k.strip()[:14]}</div></div>' for v,k in stats[1:6])
    s=re.sub(r'<div class="stats">.*?</div>\s*</div>', '<div class="stats">'+st_html+'</div>\n    </div>', s, count=1, flags=re.S)
    s=re.sub(r'<div class="pn">.*?</div>', f'<div class="pn">{a.name}</div>', s, count=1)
    en=slide_texts(slides[0])
    if len(en)>2: s=re.sub(r'<div class="en">.*?</div>', f'<div class="en">{en[2][:70]}</div>', s, count=1)
    open(H,'w').write(s)
    # 骨架 spotlight 改为按 TIM 键序映射（页数可变）
    H2=open(H).read()
    H2=H2.replace("const pid='P'+String(idx).padStart(2,'0');",
                  "const pid=Object.keys(TIM).sort()[idx];")
    open(H,'w').write(H2)
    # tim.js
    jso='const TIM='+json.dumps(tim,ensure_ascii=False)+';\nconst SPOT='+json.dumps(spot,ensure_ascii=False)+';\n'
    open(f"{D}/tim.js",'w').write(jso)
    # SPOT 校验
    bad=[(pid,i) for pid in spot for i,r in enumerate(spot[pid]) if len(r)!=2]
    # 内容完整度自检：每页 PPT shape 文字（≥8字）必须出现在生成 HTML 中
    miss=[]
    for pi in range(N):
        _,cs=build_cards(slide_texts(slides[pi]))
        page=htmlmod.unescape(title+" "+" ".join(c['title']+" "+c['body'] for c in cs))
        import re as _r3
        norm=lambda x:_r3.sub(r'[^\w一-鿿]','',x)
        for t in slide_texts(slides[pi]):
            t=htmlmod.unescape(t)
            if _r3.search(r'arXiv|P\d+\s*/\s*\d+|^\d+\s*/\s*\d+$',t): continue   # 页脚/页码排除
            if len(t)>=8 and norm(t) not in norm(page): miss.append((pi,t[:16]))
    print(f"auto_author 完成: {N}页 {sum(len(v) for v in spot.values())} 条追光映射, 格式错:{len(bad)}, PPT文字缺失:{len(miss)} {miss[:4]}")
    assert not miss and not bad, f"内容缺失/格式错: {miss[:5]}"

if __name__=='__main__': main()
