#!/usr/bin/env python3
"""快速批量 v2：原始 HTML（真实音频）+ __jump 跳帧 + 8路并行 → 1080p 成片
用法: python3 fast_batch.py --eps 09 10 21 22 23 24 25 26 27 28 29
关键：真实音频必须在场（冻结门架构靠它激活渲染层），__jump(t) 即时定位，UI 全隐藏
"""
import argparse, asyncio, glob, os, re, subprocess, shutil, tempfile

R="/Volumes/DATA/01_作品总库/AI顶级前沿论文深刻解读"
FF="/opt/homebrew/bin/ffmpeg"

HIDE_CSS="""#btnPP,#btnMute,#pbar,#pageno,#hud,.nav,#nav,.pgnav,.pagenav,#navBtns,#pgnav,
#loadmask,#subband,#subline,.pageno,.hud,button{display:none !important;}
body{cursor:none !important;}"""

def sh(c): return subprocess.run(c,capture_output=True,text=True)
def dur(p):
    r=sh(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",p])
    try: return float(r.stdout.strip())
    except: return 0.0


def rebuild_audio_zerogap(E,H):
    """零间隙直拼：段长=页界间隔（0.3s 桥会造成逐页漂移=音画错位根因）"""
    import base64
    s=open(H).read()
    b64s=re.findall(r'mkAudio\("[^"]*"\)',s) or re.findall(r'new Audio\("data:audio/mpeg;base64,([^"]+)"\)',s)
    if not b64s: return False
    b64s=[re.search(r'"([^"]+)"',x).group(1) for x in re.findall(r'mkAudio\("[^"]*"\)',s)] or b64s
    tmp=f"{E}/动态版工程/_az"; os.makedirs(tmp,exist_ok=True)
    lines=[]
    for i,b in enumerate(re.findall(r'mkAudio\("([^"]+)"\)',s) or re.findall(r'new Audio\("data:audio/mpeg;base64,([^"]+)"\)',s)):
        mp3=f"{tmp}/z{i}.mp3"; open(mp3,"wb").write(base64.b64decode(b))
        w=f"{tmp}/z{i}.wav"
        sh([FF,"-y","-i",mp3,"-ar","24000","-ac","1","-c:a","pcm_s16le",w])
        lines.append(f"file '{w}'")
    open(f"{tmp}/l.txt","w").write("\n".join(lines))
    out=f"{E}/动态版工程/voice_merged.m4a"
    sh([FF,"-y","-f","concat","-safe","0","-i",f"{tmp}/l.txt","-c:a","aac","-b:a","128k",out])
    shutil.rmtree(tmp,ignore_errors=True)
    return True

def probe(ep):
    E=os.popen(f"ls -d {R}/第{ep}期_*").read().strip()
    H=os.popen(f"ls '{E}'/*HTML动画.html 2>/dev/null | head -1").read().strip()
    if not H: return None,None,None,None
    s=open(H).read()
    m=re.search(r"TOTAL=([\d.]+)",s)
    total=float(m.group(1)) if m else None
    audio=f"{E}/动态版工程/voice_merged.m4a"
    if not os.path.exists(audio): return None,None,None,None
    if total is None: total=dur(audio)
    # 页界表
    t0=[0.0]
    for mm in re.finditer(r"_T0[=: ]+([0-9.]+)",s): t0.append(float(mm.group(1)))
    for mm in re.finditer(r't:([\d.]+),label',s): t0.append(float(mm.group(1)))
    m2=re.search(r"AUD_T0=\[([^\]]*)\]",s)
    if m2: t0 += [float(x) for x in m2.group(1).split(',')]
    t0=sorted(set(t for x in [t0] for t in x))
    return E,H,total,t0

def schedule(total,t0):
    times=set()
    def add(a,b,fps):
        a=max(0.,a); b=min(total,b)
        for i in range(int((b-a)*fps)+1):
            t=round(a+i/fps,3)
            if t<total: times.add(t)
        if b<total: times.add(round(b,3))
    add(0,12.5,30); add(12.5,min(t0[1] if len(t0)>1 else 30,total)-0.05,10)
    for pi in range(1,len(t0)):
        s0=t0[pi]; d0=(t0[pi+1]-s0) if pi+1<len(t0) else (total-s0)
        if d0<=0: continue
        add(s0,s0+5,12); add(s0+5,s0+d0-0.1,0.5); add(s0+d0-0.15,s0+d0,12)
    return sorted(t for t in times if t<total)

async def shoot(H,times,wd):
    from playwright.async_api import async_playwright
    F=f"{wd}/frames"; os.makedirs(F,exist_ok=True)
    async with async_playwright() as p:
        b=await p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required",
                                        "--use-angle=swiftshader","--disable-gpu"])
        pages=[]
        for _ in range(8):
            pg=await b.new_page(viewport={"width":1920,"height":1200})
            await pg.goto(f"file://{H}",wait_until="domcontentloaded")
            await pg.add_style_tag(content=HIDE_CSS)
            await pg.wait_for_timeout(1800)          # 等 loadmask 兜底撤除
            await pg.evaluate("window.__audioStarted=true; window.__jump(0);")
            await pg.wait_for_timeout(300)
            pages.append(pg)
        done=[0]
        async def one(pg,i,t):
            out=f"{F}/f{i:05d}.jpg"
            if os.path.exists(out) and os.path.getsize(out)>8000: return
            await pg.evaluate(f"window.__jump({t})")
            await pg.wait_for_timeout(400)            # 0.3s CSS 过渡落定
            await pg.screenshot(path=out,type="jpeg",quality=92)
            done[0]+=1
            if done[0]%300==0: print(f"    {done[0]}/{len(times)}",flush=True)
        W=len(pages)
        async def lane(pg,items):
            for i,t in items: await one(pg,i,t)
        await asyncio.gather(*[lane(pages[w],[(i,t) for i,t in enumerate(times) if i%W==w]) for w in range(W)])
        await b.close()
    miss=[i for i in range(len(times)) if not (os.path.exists(f"{F}/f{i:05d}.jpg") and os.path.getsize(f"{F}/f{i:05d}.jpg")>8000)]
    assert not miss, f"缺帧{len(miss)}"

def encode(wd,audio,out,total):
    F=f"{wd}/frames"; S=f"{wd}/seq"; os.makedirs(S,exist_ok=True)
    import bisect
    times=sorted(round(float(f[1:-4]),3) for f in os.listdir(F) if f.endswith('.jpg'))
    N=int(total*30)
    for k in range(N):
        i=bisect.bisect_right(times,k/30.0+1e-6)-1
        dst=f"{S}/s{k:05d}.jpg"
        if not os.path.exists(dst): os.link(f"{F}/f{i:05d}.jpg",dst)
    r=sh([FF,"-y","-framerate","30","-i",f"{S}/s%05d.jpg","-i",audio,
        "-vf","crop=1920:1080:0:0,format=yuv420p",
        "-c:v","libx264","-crf","19","-preset","medium","-c:a","aac","-b:a","128k",
        "-shortest",out])
    assert r.returncode==0, r.stderr[-200:]

def audit(out,total):
    from PIL import Image
    vd=dur(out)
    ok=abs(vd-total)<=6
    for tt in (total*0.3,total*0.6,total*0.9):
        fd,f=tempfile.mkstemp(suffix=".jpg"); os.close(fd)
        sh([FF,"-y","-loglevel","error","-ss",str(tt),"-i",out,"-frames:v","1","-q:v","3",f])
        im=Image.open(f).convert('RGB'); os.remove(f)
        lit=sum(1 for y in range(0,im.height,8) for x in range(0,im.width,8) if sum(im.getpixel((x,y)))>60)
        if lit/((im.height//8)*(im.width//8))<0.15: ok=False
    r=sh([FF,"-i",out,"-af","volumedetect","-f","null","-"])
    m=re.search(r"mean_volume: ([-\d.]+) dB",r.stderr)
    if not m or float(m.group(1))<-60: ok=False
    return ok,f"时长{vd:.0f}s"

def do_ep(ep):
    E,H,total,t0=probe(ep)
    assert E and H, "材料不全"
    wd=f"{E}/动态版工程"
    print(f"=== 第{ep}期 | TOTAL={total:.0f}s ===",flush=True)
    rebuild_audio_zerogap(E,H)   # 音轨零间隙重提（防漂移）
    times=schedule(total,t0)
    print(f"  采样 {len(times)} 帧（真实音频+__jump 模式）",flush=True)
    shutil.rmtree(f"{wd}/frames",ignore_errors=True); shutil.rmtree(f"{wd}/seq",ignore_errors=True)
    asyncio.run(shoot(H,times,wd))
    audio=f"{wd}/voice_merged.m4a"
    out=f"{E}/第{ep}篇_动态版_{int(total)}秒.mp4"
    encode(wd,audio,out,total)
    ok,msg=audit(out,total)
    print(f"  {'PASS' if ok else 'FAIL'} {msg} → {out}",flush=True)
    for d in ("frames","seq"): shutil.rmtree(f"{wd}/{d}",ignore_errors=True)
    return ok

if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--eps",nargs="+",required=True)
    a=ap.parse_args(); fails=[]
    for ep in a.eps:
        try:
            if not do_ep(ep): fails.append(ep)
        except Exception as e:
            print(f"第{ep}期 FAIL: {str(e)[:120]}",flush=True); fails.append(ep)
    print(f"\n完成 失败: {fails or '无'}",flush=True)
