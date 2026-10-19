#!/usr/bin/env python3
"""真实时录制：原始 HTML + 真实内嵌配音 1x 播放 → Playwright 录屏（UI 隐藏）→ 1080p 成片
用法: python3 realtime_record.py --eps 09 10 21 22 23 24 25 26 27 28 29
"""
import argparse, asyncio, glob, os, re, subprocess, shutil

R="/Volumes/DATA/01_作品总库/AI顶级前沿论文深刻解读"
FF="/opt/homebrew/bin/ffmpeg"

HIDE_CSS="""
/* 录制模式：隐藏一切 UI（按钮/进度条/页码/HUD/光标）——不该进视频 */
#btnPP,#btnMute,#pbar,#pageno,#hud,.nav,#nav,.pgnav,.pagenav,#navBtns,#pgnav,
#loadmask,#subband,#subline,.pageno,.hud{display:none !important;}
button{display:none !important;}
body{cursor:none !important;}
"""

def sh(c): return subprocess.run(c,capture_output=True,text=True)
def dur(p):
    r=sh(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",p])
    try: return float(r.stdout.strip())
    except: return 0.0

def probe(ep):
    E=os.popen(f"ls -d {R}/第{ep}期_*").read().strip()
    H=os.popen(f"ls '{E}'/*HTML动画.html 2>/dev/null | head -1").read().strip()
    if not H: return None,None,None
    s=open(H).read()
    m=re.search(r"TOTAL=([\d.]+)",s)
    total=float(m.group(1)) if m else None
    a=f"{E}/动态版工程/voice_merged.m4a"
    if not os.path.exists(a): total=None
    elif total is None: total=dur(a)
    return E,H,total

async def record(E,H,total,outdir):
    from playwright.async_api import async_playwright
    os.makedirs(outdir,exist_ok=True)
    async with async_playwright() as p:
        ctx=await p.chromium.launch(args=[
            "--autoplay-policy=no-user-gesture-required",
            "--use-angle=swiftshader","--disable-gpu"]).new_context(
            viewport={"width":1920,"height":1200},
            record_video_dir=outdir,
            record_video_size={"width":1920,"height":1200})
        pg=await ctx.new_page()
        await pg.goto(f"file://{H}",wait_until="domcontentloaded")
        await pg.add_style_tag(content=HIDE_CSS)
        # 启动：点开始按钮（如有）并解除冻结门
        await pg.evaluate("""()=>{
          window.__audioStarted=true;
          const b=[...document.querySelectorAll('button,div,span')].filter(e=>/^(▶|开始|播放)$/i.test(e.textContent.trim()));
          if(b.length)b[0].click();
          try{if(window._vo&&_vo.paused)_vo.play();}catch(e){}
          document.querySelectorAll('audio').forEach(a=>a.play().catch(()=>{}));
        }""")
        # 真实时播放到结尾 + 3s 缓冲
        await pg.wait_for_timeout(int((total+3)*1000))
        v=pg.video
        path=await v.path()
        await ctx.close()
        return path

def finalize(rec, audio, out):
    sh([FF,"-y","-i",rec,"-i",audio,
        "-vf","crop=1920:1080:0:0,fps=30,format=yuv420p",
        "-c:v","libx264","-crf","19","-preset","medium",
        "-c:a","aac","-b:a","128k","-shortest",out])

def do_ep(ep):
    E,H,total=probe(ep)
    assert E and H and total, f"第{ep}期 材料不全"
    wd=f"{E}/动态版工程/_rec"; shutil.rmtree(wd,ignore_errors=True)
    print(f"=== 第{ep}期 {os.path.basename(H)} | {total:.0f}s 实时录制 ===",flush=True)
    rec=asyncio.run(record(E,H,total,wd))
    audio=f"{E}/动态版工程/voice_merged.m4a"
    out=f"{E}/第{ep}篇_动态版_{int(total)}秒.mp4"
    finalize(rec,audio,out)
    vd=dur(out)
    # 抽帧亮度自检（真实播放，内容必须>25%）
    ok=vd>total*0.95
    import tempfile
    from PIL import Image
    for tt in (total*0.3,total*0.6,total*0.9):
        fd,f=tempfile.mkstemp(suffix=".jpg"); os.close(fd)
        sh([FF,"-y","-loglevel","error","-ss",str(tt),"-i",out,"-frames:v","1","-q:v","3",f])
        im=Image.open(f).convert('RGB'); os.remove(f)
        lit=sum(1 for y in range(0,im.height,8) for x in range(0,im.width,8) if sum(im.getpixel((x,y)))>60)
        if lit/((im.height//8)*(im.width//8))<0.15: ok=False
    print(f"  {'PASS' if ok else 'FAIL'} 时长{vd:.0f}s → {out}",flush=True)
    shutil.rmtree(wd,ignore_errors=True)
    return ok

if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--eps",nargs="+",required=True)
    a=ap.parse_args(); fails=[]
    for ep in a.eps:
        try:
            if not do_ep(ep): fails.append(ep)
        except Exception as e:
            print(f"第{ep}期 FAIL: {e}",flush=True); fails.append(ep)
    print(f"\n完成 失败: {fails or '无'}",flush=True)
