#!/usr/bin/env python3
"""paper-anim-video 一键出片：采样帧表 → Playwright 截图 → 30fps 硬链接展开 → 编码合配音
用法: python3 make_video.py --dir /path/工程目录 [--out 成片.mp4]
依赖: playwright; 页面需支持 ?t= 定帧（模板已内置冻结过渡）。
"""
import asyncio, os, sys, json, bisect, subprocess, argparse

CHROME_ARGS=["--use-angle=swiftshader"]

def probe_dur(p):
    r=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",p],capture_output=True,text=True)
    return float(r.stdout.strip())

def build_schedule(D, total, pages_d, tim, T0=None):
    CUM=[0]
    for d in pages_d: CUM.append(CUM[-1]+d)
    times=set()
    def add(a,b,fps):
        a=max(0.,a); b=min(total,b)
        for i in range(int((b-a)*fps)+1):
            t=round(a+i/fps,3)
            if t<total: times.add(t)
        if b<total: times.add(round(b,3))
    if T0 is None: T0=CUM
    add(0,12.5,30); add(12.5,T0[1]-0.05,10)
    vkeys=sorted(tim.keys())
    for pi in range(1,len(pages_d)):
        pid=vkeys[pi] if pi<len(vkeys) else f"P{pi:02d}"
        s=T0[pi] if pi<len(T0) else CUM[pi]; d=pages_d[pi]
        add(s,s+5,12)
        for b in tim[pid]:
            bs=s+b["start"]; add(bs-0.1,bs+0.6,10)
        add(s+5,s+d-0.1,0.5); add(s+d-0.15,s+d,12)
    return sorted(t for t in times if 0<=t<total)

CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
def shot_chrome(args):
    """Chrome CLI 单帧：后台启动+轮询文件写稳即杀（不依赖 Chrome 正常退出，任何环境可用）"""
    import time
    D, html, i, t = args
    out=f"{D}/frames/f{i:05d}.jpg"
    if os.path.exists(out) and os.path.getsize(out)>8000: return
    prof=f"/tmp/pav_f{i%64}"   # 滚动64个独立profile,避免锁竞争
    for _ in range(3):
        try: os.remove(out)
        except: pass
        pr=subprocess.Popen([CHROME,"--headless","--use-angle=swiftshader","--disable-gpu",
            f"--user-data-dir={prof}","--screenshot="+out,"--window-size=1920,1200",
            "--hide-scrollbars","--virtual-time-budget=6000",f"{html}?t={t}"],
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for _ in range(48):
            time.sleep(0.5)
            if os.path.exists(out) and os.path.getsize(out)>20000:
                sz=os.path.getsize(out); time.sleep(1.2)
                if os.path.getsize(out)==sz: break
        pr.kill()
        try: os.remove(f"{prof}/SingletonLock")
        except: pass
        if os.path.exists(out) and os.path.getsize(out)>8000: return
    raise RuntimeError(f"frame fail t={t}")

def shoot_chrome_parallel(D, html, times, workers=8):
    from concurrent.futures import ThreadPoolExecutor
    F=f"{D}/frames"; os.makedirs(F,exist_ok=True)
    with ThreadPoolExecutor(workers) as ex:
        n=0
        for _ in ex.map(shot_chrome, ((D,html,i,t) for i,t in enumerate(times))):
            n+=1
            if n%200==0: print("shot",n,"/",len(times),flush=True)

async def shoot(D, html, times):
    from playwright.async_api import async_playwright
    F=f"{D}/frames"; os.makedirs(F,exist_ok=True)
    async with async_playwright() as p:
        b=await p.chromium.launch(args=CHROME_ARGS)
        pages=[await b.new_page(viewport={"width":1920,"height":1200}) for _ in range(8)]
        for pg in pages:
            await pg.goto(f"file://{html}?t=0",wait_until="domcontentloaded")
            await pg.wait_for_timeout(400)
        sem=asyncio.Semaphore(8); done=[0]
        async def one(pg,i,t):
            async with sem:
                out=f"{F}/f{i:05d}.jpg"
                if os.path.exists(out) and os.path.getsize(out)>8000: return
                await pg.evaluate(f"window.__seekT={t}")
                await pg.wait_for_timeout(70)
                await pg.screenshot(path=out,type="jpeg",quality=92)
                done[0]+=1
                if done[0]%200==0: print("shot",done[0],"/",len(times),flush=True)
        # 按页签分队列：路间并行、路内串行（避免同页导航互撞）
        W=len(pages)
        async def lane(pg, items):
            for i,t in items:
                await one(pg,i,t)
        await asyncio.gather(*[lane(pages[w], [(i,t) for i,t in enumerate(times) if i%W==w]) for w in range(W)])
        await b.close()
    missing=[i for i in range(len(times)) if not (os.path.exists(f"{F}/f{i:05d}.jpg") and os.path.getsize(f"{F}/f{i:05d}.jpg")>8000)]
    assert not missing, f"缺帧 {len(missing)}: {missing[:8]}"

def expand_seq(D, times, total):
    F,S=f"{D}/frames",f"{D}/seq"; os.makedirs(S,exist_ok=True)
    N=int(total*30)
    for k in range(N):
        i=bisect.bisect_right(times,k/30.0+1e-6)-1
        dst=f"{S}/s{k:05d}.jpg"
        if not os.path.exists(dst): os.link(f"{F}/f{i:05d}.jpg",dst)
    return N

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--dir",required=True); ap.add_argument("--out",default=None)
    ap.add_argument("--engine",default="chrome",choices=["chrome","playwright"])
    ap.add_argument("--workers",type=int,default=8)
    a=ap.parse_args()
    cfg=open(f"{a.dir}/project_config.py").read()
    ns={}; exec(cfg,ns)
    total=ns["TOTAL"]; pages_d=ns["PAGES"]; T0=ns.get("T0")
    tim=json.load(open(f"{a.dir}/tim_data.json"))
    html=f"{a.dir}/render_src.html" if os.path.exists(f"{a.dir}/render_src.html") else f"{a.dir}/bert_anim.html"
    audio=f"{a.dir}/voice_full.m4a"
    times=build_schedule(a.dir,total,pages_d,tim,T0=T0)
    print("采样帧:",len(times),flush=True)
    if a.engine=="chrome":
        shoot_chrome_parallel(a.dir,f"file://{html}",times,a.workers)
    else:
        asyncio.run(shoot(a.dir,html,times))
    N=expand_seq(a.dir,times,total)
    print("30fps 序列:",N,flush=True)
    out=a.out or f"{a.dir}/成片_{int(total)}s.mp4"
    subprocess.run(["/opt/homebrew/bin/ffmpeg","-y","-framerate","30","-i",f"{a.dir}/seq/s%05d.jpg","-i",audio,
        "-vf","crop=1920:1080:0:0,format=yuv420p","-c:v","libx264","-crf","19","-preset","medium",
        "-c:a","aac","-b:a","128k","-shortest",out],check=True)
    print("DONE →",out)

if __name__=="__main__": main()
