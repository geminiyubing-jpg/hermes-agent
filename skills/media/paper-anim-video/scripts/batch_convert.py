#!/usr/bin/env python3
"""批量：论文 HTML 动画（内嵌配音的合并版）→ 视频，串行逐集，防空音
用法: python3 batch_convert.py --eps 09 10 21 22 23 24 25 26 27 28 29
每集: ①提取内嵌配音段→合并音轨（段间 0.3s 静音，防串页双声/空音）
      ②建 render_src（音频哑化+seekT+渲染门） ③8路截图 ④30fps 硬链接+x264+音轨
      ⑤审计（时长/黑页/音频非空）⑥归档各自论文文件夹
"""
import argparse, asyncio, base64, json, os, re, subprocess, sys, tempfile, shutil

R="/Volumes/DATA/01_作品总库/AI顶级前沿论文深刻解读"
FF="/opt/homebrew/bin/ffmpeg"; CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

def sh(c,**k): return subprocess.run(c,capture_output=True,text=True,**k)
def dur(p):
    r=sh(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",p])
    try: return float(r.stdout.strip())
    except: return 0.0

def probe(ep):
    E=os.popen(f"ls -d {R}/第{ep}期_*").read().strip()
    H=os.popen(f"ls -t '{E}'/*HTML动画.html 2>/dev/null | head -1").read().strip()
    if not H: return None,None,None
    s=open(H).read()
    m=re.search(r"TOTAL=([0-9.]+)",s)
    total=float(m.group(1)) if m else None
    # 页界：PAGES 数组的 t: 值 或 xxx_T0= 值
    t0=[0.0]
    for mm in re.finditer(r"_T0[=: ]+([0-9.]+)",s): t0.append(float(mm.group(1)))
    for mm in re.finditer(r't:([\d.]+),label',s): t0.append(float(mm.group(1)))
    t0=sorted(set(t0))
    return E,H,total,t0

def extract_audio(ep,H,E):
    """内嵌 base64 mp3 按页序提出，cat 成一条音轨（页间 0.3s 静音桥）"""
    s=open(H).read()
    b64s=re.findall(r'mkAudio\("([^"]+)"\)',s)
    if not b64s:
        b64s=re.findall(r'new Audio\("data:audio/mpeg;base64,([^"]+)"\)',s)
    if not b64s: return None
    tmp=f"{E}/动态版工程/_audio_tmp"; os.makedirs(tmp,exist_ok=True)
    parts=[]
    for i,b in enumerate(b64s):
        mp3=f"{tmp}/a{i:02d}.mp3"; open(mp3,"wb").write(base64.b64decode(b))
        parts.append(mp3)
    # 拼接：逐段转 wav + 0.3s 桥 → concat
    lst=f"{tmp}/list.txt"; lines=[]
    for i,p in enumerate(parts):
        w=f"{tmp}/a{i:02d}.wav"
        sh([FF,"-y","-i",p,"-ar","24000","-ac","1","-c:a","pcm_s16le",w])
        lines.append(f"file '{w}'")
        gap=f"{tmp}/g{i:02d}.wav"
        sh([FF,"-y","-f","lavfi","-i","anullsrc=r=24000:cl=mono","-t","0.3",gap])
        lines.append(f"file '{gap}'")
    open(lst,"w").write("\n".join(lines))
    out=f"{E}/动态版工程/voice_merged.m4a"
    sh([FF,"-y","-f","concat","-safe","0","-i",lst,"-c:a","aac","-b:a","128k",out])
    shutil.rmtree(tmp,ignore_errors=True)
    return out


def audio_gate_stub(s):
    """音频驱动型文件：stub 的 currentTime 跟随 window.__seekT（按段位表换算偏移）"""
    # 段位表优先级：AUD_T0 > PAGE_AUDIO > _T0 值
    t0=None
    m=re.search(r"AUD_T0=\[([^\]]*)\]",s)
    if m: t0=[float(x) for x in m.group(1).split(',')]
    if not t0:
        m=re.search(r"PAGE_AUDIO=(\[\[.*?\]\])",s)
        if m: t0=[float(x) for x in re.findall(r"\[([\d.]+)",m.group(1))]
    return t0

def make_render_src(H,E):
    s=open(H).read()
    stub='({currentTime:0,readyState:4,paused:true,ended:true,duration:0,play(){return Promise.resolve()},pause(){},})'
    t0list=audio_gate_stub(s)
    n=re.subn(r'mkAudio\("[^"]*"\)','',s)[1]
    n2=re.subn(r'new Audio\("data:audio/mpeg;base64,[^"]*"\)','',s)[1]
    if t0list and len(t0list)>=2:
        # 音频驱动型：按段位表生成带 currentTime getter 的 stub（seekT 全局时间→段内偏移）
        arr='['+','.join(str(x) for x in t0list)+']'
        idx=[0]
        def rep(m):
            i=idx[0]; idx[0]+=1
            return f'__gate({i})'
        s=re.sub(r'mkAudio\("[^"]*"\)',rep,s)
        s=re.sub(r'new Audio\("data:audio/mpeg;base64,[^"]*"\)',rep,s)
        gate=f"""<script>
window.__T0={arr};
window.__gate=function(i){{ const t0=window.__T0[i]||0, t1=window.__T0[i+1]||1e9;
  return {{ get currentTime(){{ const T=(window.__seekT||0); return Math.max(0,Math.min(T-t0,t1-t0)); }},
    readyState:4, paused:false, ended:false, duration:9999,
    play(){{return Promise.resolve()}}, pause(){{}}, }}; }};
</script>"""
        s=s.replace("<script>",gate+"<script>",1)
    else:
        s=re.sub(r'mkAudio\("[^"]*"\)',f'__d={stub}',s)
        s=re.sub(r'new Audio\("data:audio/mpeg;base64,[^"]*"\)',f'__d={stub}',s)
    # seekT 注入：所有「t 从 URL 读取」的行前加 seekT 覆盖
    mode='seek'
    key="if(!window.__qpOff && _qp.get('t')!==null) t=parseFloat(_qp.get('t'));"
    if key in s:
        s=s.replace(key,"if(window.__seekT!==undefined) t=window.__seekT;\n    else "+key)
    else:
        # 兜底：任何 location/search 解析 t 的赋值后挂 seekT
        m=re.search(r'(t\s*=\s*parseFloat\([^)]*get\([^)]*\'t\'[^)]*\)[^;]*;)',s)
        if m:
            s=s.replace(m.group(1), f"if(window.__seekT!==undefined) t=window.__seekT; else {m.group(1)}",1)
        else:
            mode='url'   # 无注入口 → 截图走 URL 逐帧
    # 渲染门
    s=re.sub(r"function loop\(now\)\{",
             "function loop(now){\n    if(window.__seekT!==undefined){ if(window.__lastSeek===window.__seekT){requestAnimationFrame(loop);return;} window.__lastSeek=window.__seekT; }",
             s,count=1)
    out=f"{E}/动态版工程/render_src.html"; os.makedirs(f"{E}/动态版工程",exist_ok=True)
    open(out,"w").write(s)
    return out,n+n2,mode

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
        add(s0,s0+5,12); add(s0+5,s0+d0-0.1,0.5); add(s0+d0-0.15,s0+d0,12)
    return sorted(t for t in times if t<total)

async def shoot(src,times,workdir,mode='seek'):
    from playwright.async_api import async_playwright
    F=f"{workdir}/frames"; os.makedirs(F,exist_ok=True)
    async with async_playwright() as p:
        b=await p.chromium.launch(args=["--use-angle=swiftshader","--disable-gpu"])
        pages=[await b.new_page(viewport={"width":1920,"height":1200}) for _ in range(8)]
        for pg in pages:
            await pg.goto(f"file://{src}?t=0",wait_until="domcontentloaded")
            await pg.wait_for_timeout(500)
        done=[0]
        async def one(pg,i,t):
            out=f"{F}/f{i:05d}.jpg"
            if os.path.exists(out) and os.path.getsize(out)>8000: return
            if mode=='seek':
                await pg.evaluate(f"window.__seekT={t}")
                await pg.wait_for_timeout(70)
            else:
                await pg.goto(f"file://{src}?t={t}",wait_until="domcontentloaded")
                await pg.wait_for_timeout(450)
            await pg.screenshot(path=out,type="jpeg",quality=92)
            done[0]+=1
            if done[0]%300==0: print(f"    {done[0]}/{len(times)}",flush=True)
        W=len(pages)
        async def lane(pg,items):
            for i,t in items:
                for _ in range(3):
                    try: await one(pg,i,t); break
                    except Exception: await pg.goto(f"file://{src}?t=0",wait_until="domcontentloaded")
        await asyncio.gather(*[lane(pages[w],[(i,t) for i,t in enumerate(times) if i%W==w]) for w in range(W)])
        await b.close()
    missing=[i for i in range(len(times)) if not (os.path.exists(f"{F}/f{i:05d}.jpg") and os.path.getsize(f"{F}/f{i:05d}.jpg")>8000)]
    assert not missing, f"缺帧 {len(missing)}"

def encode(workdir,audio,out,total):
    F=f"{workdir}/frames"; S=f"{workdir}/seq"; os.makedirs(S,exist_ok=True)
    import bisect
    times=sorted(round(float(f[1:-4]),3) for f in os.listdir(F) if f.endswith('.jpg'))
    N=int(total*30)
    for k in range(N):
        i=bisect.bisect_right(times,k/30.0+1e-6)-1
        dst=f"{S}/s{k:05d}.jpg"
        if not os.path.exists(dst): os.link(f"{F}/f{i:05d}.jpg",dst)
    r=sh([FF,"-y","-framerate","30","-i",f"{S}/s%05d.jpg","-i",audio,
        "-vf","scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,format=yuv420p",
        "-c:v","libx264","-crf","19","-preset","medium","-c:a","aac","-b:a","128k",
        "-shortest",out])
    assert os.path.exists(out) and r.returncode==0, r.stderr[-300:]

def audit(out,total):
    vd=dur(out)
    ok=abs(vd-total)<=6
    # 黑页抽帧
    import tempfile as tf
    bad=0
    for tt in (total*0.2,total*0.5,total*0.8):
        fd,f=tf.mkstemp(suffix=".jpg"); os.close(fd)
        sh([FF,"-y","-loglevel","error","-ss",str(tt),"-i",out,"-frames:v","1","-q:v","3",f])
        from PIL import Image
        im=Image.open(f).convert("RGB"); os.remove(f)
        lit=sum(1 for y in range(0,im.height,8) for x in range(0,im.width,8) if sum(im.getpixel((x,y)))>60)
        if lit/((im.height//8)*(im.width//8))<0.25: bad+=1
    # 音频非空（ RMS 电平）
    r=sh([FF,"-i",out,"-af","volumedetect","-f","null","-"])
    m=re.search(r"mean_volume: ([-\d.]+) dB",r.stderr)
    mean=float(m.group(1)) if m else -99
    return ok and bad==0 and mean>-60, f"时长{vd:.0f}/{total:.0f}s 黑页{bad} 音频{mean}dB"

def do_ep(ep):
    E,H,total,t0=probe(ep)
    assert E and H, f"第{ep}期 未找到 HTML"
    print(f"=== 第{ep}期 {os.path.basename(E)} | {os.path.basename(H)} | TOTAL={total} ===",flush=True)
    wd=f"{E}/动态版工程"
    audio=extract_audio(ep,H,E)
    assert audio and dur(audio)>30, "配音提取失败/过短"
    if total is None: total=dur(audio)   # 无 TOTAL 标记：以合并音轨实长为准
    src,na,mode=make_render_src(H,E)
    times=schedule(total,t0)
    print(f"  配音{dur(audio):.0f}s 哑化{na}处 模式={mode} 采样{len(times)}帧",flush=True)
    asyncio.run(shoot(src,times,wd,mode))
    out=f"{E}/第{ep}篇_动态版_{int(total)}秒.mp4"
    encode(wd,audio,out,total)
    ok,msg=audit(out,total)
    print(f"  {'PASS' if ok else 'FAIL'} {msg} → {out}",flush=True)
    # 清帧
    for d in ("frames","seq"): shutil.rmtree(f"{wd}/{d}",ignore_errors=True)
    return ok

if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--eps",nargs="+",required=True)
    a=ap.parse_args()
    fails=[]
    for ep in a.eps:
        try:
            if not do_ep(ep): fails.append(ep)
        except Exception as e:
            print(f"第{ep}期 FAIL: {e}",flush=True); fails.append(ep)
    print(f"\n批量完成 失败: {fails or '无'}",flush=True)
