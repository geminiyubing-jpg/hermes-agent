#!/usr/bin/env python3
"""paper-anim-video 成片审计：抽帧验证片头海报与飞卡 = 本篇封面（防串封面/旧帧）
用法: python3 audit_episode.py --video 成片.mp4 --ep N [--covers covers目录]
判据：t=4.7 海报帧与 ep{NN}_169 差异最小；t=3.0 前卡与 ep{NN}.jpg 差异最小。
"""
import argparse, subprocess, os, re, tempfile
from PIL import Image

def crop_center(im, r=140):
    w,h=im.size
    return im.crop((w//2-r, h//2-int(r*4/3), w//2+r, h//2+int(r*4/3))).resize((60,80))

def diff(a,b):
    n=0
    for y in range(80):
        for x in range(60):
            ca,cp=a.getpixel((x,y)),b.getpixel((x,y))
            n+=sum(abs(ca[i]-cp[i]) for i in range(3))
    return n/(60*80*3)

def frame_at(video,t):
    fd,f=tempfile.mkstemp(suffix=".jpg"); os.close(fd)
    subprocess.run(["/opt/homebrew/bin/ffmpeg","-y","-loglevel","error","-ss",str(t),
                    "-i",video,"-frames:v","1","-q:v","3",f],check=True)
    return f

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--video",required=True); ap.add_argument("--ep",type=int,required=True)
    ap.add_argument("--covers",default="/Volumes/DATA/temp/20260917_论文引擎工程/bert_anim/covers")
    a=ap.parse_args()
    nn=f"{a.ep:02d}"; others=[f"{a.ep-1:02d}",f"{a.ep+1:02d}"]
    ok=True; msgs=[]
    # 海播 t=4.7
    f=frame_at(a.video,4.7)
    shot=crop_center(Image.open(f).convert("RGB")); os.remove(f)
    scores={c:diff(shot,crop_center(Image.open(f"{a.covers}/ep{c}_169.jpg").convert("RGB")))
            for c in [nn]+others if os.path.exists(f"{a.covers}/ep{c}_169.jpg")}
    best=min(scores,key=scores.get)
    if best!=nn: ok=False
    msgs.append(f"海报@4.7s={best}({'应'+nn}) {scores}")
    # 前卡 t=3.0（弱信号，仅参考）
    f=frame_at(a.video,3.0)
    shot=crop_center(Image.open(f).convert("RGB")); os.remove(f)
    scores2={c:diff(shot,crop_center(Image.open(f"{a.covers}/ep{c}.jpg").convert("RGB")))
             for c in [nn]+others if os.path.exists(f"{a.covers}/ep{c}.jpg")}
    best2=min(scores2,key=scores2.get)
    msgs.append(f"前卡@3.0s={best2}(参考) {({k:round(v) for k,v in scores2.items()})}")
    # ② 时长 = project_config TOTAL ±1.5s
    import glob as _g
    cfg=_g.glob(a.video.rsplit("/",2)[0]+"/project_config.py")
    if cfg:
        ns={}; exec(open(cfg[0]).read(),ns)
        vd=float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",a.video],capture_output=True,text=True).stdout.strip())
        m3=f"时长 {vd:.1f}s (应{ns['TOTAL']}s)"
        if abs(vd-ns['TOTAL'])>1.5: ok=False; m3+=" ✗"
        msgs.append(m3)
    # ③ 内容页亮度：抽 3 个正文页中点帧，中亮像素须 >30%（防黑页）
    import tempfile as _tf
    cfg2=_g.glob(a.video.rsplit("/",2)[0]+"/project_config.py")
    cum=[0]
    if cfg2:
        ns={}; exec(open(cfg2[0]).read(),ns)
        for d_ in ns['PAGES']: cum.append(cum[-1]+d_)
        for pi in (2, len(ns['PAGES'])//2, len(ns['PAGES'])-1):
            tt=cum[pi]+min(ns['PAGES'][pi]-1,5)
            f2=frame_at(a.video,tt)
            im=Image.open(f2).convert("RGB"); os.remove(f2)
            w,h=im.size; mid=0
            for y in range(0,h,6):
                for x in range(0,w,6):
                    if sum(im.getpixel((x,y)))>60: mid+=1
            pct=100*mid/((h//6)*(w//6))
            m4=f"内容页{pi}@{tt:.0f}s 中亮{pct:.0f}%"
            if pct<30: ok=False; m4+=" ✗"
            msgs.append(m4)
    # ④ PPT 内容完整度：每页 shape 文字（≥8字）须出现在动画 HTML
    h=_g.glob(a.video.rsplit("/",1)[0]+"/bert_anim.html")
    if h and _g.glob(a.video.rsplit("/",2)[0]):
        import re as _r2
        html=_r2.sub(r'\s','',open(h[0]).read())
        LIB="/Volumes/DATA/temp/20260917_论文引擎工程"
        sl=sorted(_g.glob(f"{LIB}/ep{int(a.ep)}_v2/slides-html/slide-*.html"))
        miss=0; tot=0
        for f in sl:
            for t in re.findall(r'class="shape txt[^"]*" style="[^"]*">([^<]*)<',open(f).read()):
                t2=t.replace("&quot;",'"').replace("&#39;","'").replace("&amp;","&").strip()
                if len(t2)>=8:
                    tot+=1
                    if _r2.sub(r'\s','',t2) not in html: miss+=1
        m5=f"PPT内容覆盖 {tot-miss}/{tot}"
        if tot and miss/max(tot,1)>0.02: ok=False; m5+=" ✗"
        msgs.append(m5)
    print(("PASS " if ok else "FAIL ")+a.video.split("/")[-1])
    for m in msgs: print("   ",m)
    raise SystemExit(0 if ok else 1)

if __name__=="__main__": main()
