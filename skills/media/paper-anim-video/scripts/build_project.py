#!/usr/bin/env python3
"""paper-anim-video 一键建工程：解说稿 → 配音 → 工程目录（HTML骨架+时长+时间戳+渲染脚本）
用法:
  python3 build_project.py --script /path/第XX篇_解说稿.md --ep 3 --target 3 --out /path/工程目录
产物: OUT/{voice wavs, voice_full.m4a, tim_data.json, tim.js, bert_anim.html, render_fast.sh, times由渲染脚本生成}
之后: agent 按 SKILL.md 填写 13 页 scene 内容与 SPOT 映射 → ./render_fast.sh 出片
"""
import asyncio, subprocess, re, json, os, sys, argparse, shutil
import re as _r  # 断句用

TPL = "/Volumes/DATA/temp/20260917_论文引擎工程/bert_anim"   # BERT 样板工程
VOICE, RATE, GAP = "zh-CN-XiaoxiaoNeural", "+8%", 0.18

def sh(c): return subprocess.run(c, capture_output=True, text=True)
def dur(p):
    r = sh(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",p])
    try: return float(r.stdout.strip())
    except: return 0.0
def cw(a): return sum(0.3 if c in "，。：；、" else (0.6 if (c.isascii() and (c.isalnum() or c==" ")) else 1.0) for c in a)
def split_natural(t):
    parts=[p for p in re.split(r'(?<=[，。：；、])',t) if p]
    merged=[]
    for ck in parts:
        hang=merged and _r.search(r'[的在了和与或是把被将又也还]$',merged[-1])   # 句尾虚词悬挂→并入下句
        if merged and (hang or cw(merged[-1])<4.5 or cw(ck)<4.5) and cw(merged[-1])+cw(ck)<=28:
            merged[-1]+=ck
        else: merged.append(ck)
    return merged

async def synth_page(D, pid, text):
    import edge_tts
    chunks=[]
    for s in [s for s in re.split(r'(?<=。)',text) if s.strip()]: chunks.extend(split_natural(s))
    wavs, tim, t = [], [], 0.0
    for i,ck in enumerate(chunks):
        mp3,wav=f"{D}/{pid}n_{i}.mp3",f"{D}/{pid}n_{i}.wav"
        for _ in range(4):
            await edge_tts.Communicate(ck,VOICE,rate=RATE).save(mp3)
            if dur(mp3)>0.3: break
        sh(["ffmpeg","-y","-i",mp3,"-ar","24000","-ac","1","-c:a","pcm_s16le",wav])
        d=dur(wav); tim.append(dict(text=ck,start=round(t,2),dur=round(d,2))); t+=d; wavs.append(wav)
        if i<len(chunks)-1:
            g=f"{D}/{pid}n_gap_{i}.wav"
            sh(["ffmpeg","-y","-f","lavfi","-i","anullsrc=r=24000:cl=mono","-t",str(GAP),g]); wavs.append(g); t+=GAP
    open(f"{D}/{pid}n_list.txt","w").write("\n".join(f"file '{p}'" for p in wavs))
    sh(["ffmpeg","-y","-f","concat","-safe","0","-i",f"{D}/{pid}n_list.txt","-ar","24000","-ac","1","-c:a","pcm_s16le",f"{D}/{pid}_voice.wav"])
    return tim

async def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--script",required=True); ap.add_argument("--out",required=True)
    ap.add_argument("--ep",type=int,required=True); ap.add_argument("--target",type=int,help="片头扑克目标=篇号,默认=ep")
    ap.add_argument("--name",default=None,help="论文短名")
    a=ap.parse_args(); a.target=a.target or a.ep
    short_name=a.name or f"EP{a.ep:02d}"
    os.makedirs(a.out,exist_ok=True)
    raw=open(a.script).read()
    pages=re.findall(r'## (P\d{2})[^\n]*\n+(.*?)(?=\n## |\Z)', raw, re.S)
    assert pages and len(pages)>=12, f"解说稿需 P00-P12 分段, 现解析到 {len(pages)} 段"
    all_tim={}; durs={}
    for pid,txt in pages:
        text=re.sub(r'\s+','',txt)
        all_tim[pid]=await synth_page(a.out,pid,text)
        durs[pid]=round(all_tim[pid][-1]["start"]+all_tim[pid][-1]["dur"],2)
        print(pid,"blocks:",len(all_tim[pid]),"dur:",durs[pid],flush=True)
    json.dump(all_tim,open(f"{a.out}/tim_data.json","w"),ensure_ascii=False)
    open(f"{a.out}/vo_concat.txt","w").write("\n".join(f"file '{pid}_voice.wav'" for pid,_ in pages))
    sh(["ffmpeg","-y","-f","concat","-safe","0","-i",f"{a.out}/vo_concat.txt","-c:a","aac","-b:a","128k",f"{a.out}/voice_full.m4a"])
    total=round(sum(durs.values()),2)
    # 从样板复制骨架并注入本篇参数
    html=open(f"{TPL}/bert_anim.html").read()
    html=re.sub(r"const CIN=\{N:25,TARGET:\d+,", f"const CIN={{N:25,TARGET:{a.target},", html)
    import re as _re
    html=_re.sub(r"ep\d+(_169)?\.jpg", lambda m: f"ep{a.target:02d}{m.group(1) or ''}.jpg", html)
    newpages=",".join(f"['{pid}',r{int(pid[1:]):02d},{durs[pid]:.2f}]" for pid,_ in pages)
    html=re.sub(r"const PAGES=\[.*?\];", f"const PAGES=[{newpages}];", html, flags=re.S)
    # 渲染函数名占位：保留 r00..r12（内容待 agent 按 SKILL.md 替换 scene）
    # 篇名残留清理（模板来自 BERT 样板，三处必改：title/hud/brand）
    import re as _re
    html=_re.sub(r"<title>[^<]*</title>", f"<title>{short_name} 深度解读</title>", html)
    html=_re.sub(r"\$\{PAGES\[idx\]\[0\]\}", "${PAGES[idx][0]}", html)
    html=html.replace("BERT 深度解读 · <b>", f"{short_name} 深度解读 · <b>")
    html=_re.sub(r'<div class="brand">[^<]*</div>',
                 f'<div class="brand">{short_name} · 论文动态解读</div>', html)
    open(f"{a.out}/bert_anim.html","w").write(html)

    # tim.js（TIM 注入；SPOT 留空映射待 agent 填）
    js="const TIM="+json.dumps(all_tim,ensure_ascii=False)+";\nconst SPOT={"+",".join(f"'{pid}':[]" for pid,_ in pages)+"};\n"
    open(f"{a.out}/tim.js","w").write(js)
    # 渲染脚本随 skill 提供
    sk=os.path.dirname(os.path.abspath(__file__))
    shutil.copy(f"{sk}/make_video.py", f"{a.out}/make_video.py")
    # covers 软链共用
    if not os.path.exists(f"{a.out}/covers"): os.symlink(f"{TPL}/covers", f"{a.out}/covers")
    cfg=f'D="{a.out}"\nTOTAL={total}\nPAGES={[durs[p] for p,_ in pages]}\n'
    open(f"{a.out}/project_config.py","w").write(cfg)
    print(f"\n工程就绪: {a.out}\n页时长: {durs}\n总时长: {total}s\n下一步: 填写 bert_anim.html 各页 scene 内容 + tim.js SPOT 映射 → 跑 render_video.py")

asyncio.run(main())
