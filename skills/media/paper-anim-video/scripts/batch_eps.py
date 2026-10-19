#!/usr/bin/env python3
"""paper-anim-video 批量流水线：解说稿+PPT → 配音 → 自动布局 → 渲染 → 归档
用法: python3 batch_eps.py --eps 5 6 7 ... --engine playwright
每集产物: 第NN期_XXX/动态版工程/ + 第NN篇_动态版_XXX秒.mp4
"""
import argparse, subprocess, os, sys, glob, re, json, time

SK="/Volumes/DATA/hermes-agent-main/skills/media/paper-anim-video/scripts"
LIB="/Volumes/DATA/temp/20260917_论文引擎工程"
ROOT="/Volumes/DATA/01_作品总库/B号今天也知道了_新号/AI顶级前沿论文深刻解读"
VENV="/Volumes/DATA/hermes-agent-main/.venv/bin/python3"
PY=sys.executable

def ep_dir(ep):
    d=glob.glob(f"{ROOT}/通俗易懂聊顶刊AI-第{ep:02d}期_*")
    return d[0] if d else None

def ep_name(ep):
    d=ep_dir(ep)
    m=re.search(r'第\d+期_(.+)$',d)
    return m.group(1)

def run(cmd,**kw):
    r=subprocess.run(cmd,capture_output=True,text=True,**kw)
    if r.returncode!=0:
        print(r.stdout[-1500:]); print(r.stderr[-1500:]); raise RuntimeError(f"FAIL: {' '.join(cmd[:4])}")
    return r.stdout

def do_ep(ep,engine):
    t0=time.time(); d=ep_dir(ep); name=ep_name(ep)
    out=f"{d}/动态版工程"
    script=glob.glob(f"{d}/第{ep:02d}篇_解说稿.md")[0]
    slides=f"{LIB}/ep{ep}_v2/slides-html"
    print(f"=== EP{ep:02d} {name} ===",flush=True)
    if not os.path.exists(f"{out}/voice_full.m4a"):
        run([VENV,f"{SK}/build_project.py","--script",script,"--ep",str(ep),"--out",out])
    if not os.path.exists(f"{out}/.authored"):
        run([PY,f"{SK}/auto_author.py","--dir",out,"--slides",slides,"--name",name])
        open(f"{out}/.authored","w").write("ok")
    ns={}; exec(open(f"{out}/project_config.py").read(),ns); dur=int(ns["TOTAL"])
    mp4=f"{out}/第{ep:02d}篇_动态版_{dur}秒.mp4"
    if not os.path.exists(mp4):
        run([PY,f"{SK}/make_video.py","--dir",out,"--engine",engine,"--out",mp4],timeout=7200)
    # 归档到论文文件夹根
    import shutil; dst=f"{d}/第{ep:02d}篇_动态版_{dur}秒.mp4"
    if not os.path.exists(dst): shutil.copy(mp4,dst)
    # 清帧省空间
    # 成片审计：海报/飞卡必须=本篇封面（防串封面、防旧帧复用）
    r=subprocess.run([PY,f"{SK}/audit_episode.py","--video",dst,"--ep",str(ep)],capture_output=True,text=True)
    print(r.stdout.strip(),flush=True)
    if r.returncode!=0:
        print(f"EP{ep:02d} 审计FAIL：清理该集全部帧待重渲",flush=True)
        import shutil as _sh2
        _sh2.rmtree(f"{out}/frames",ignore_errors=True); _sh2.rmtree(f"{out}/seq",ignore_errors=True)
        raise RuntimeError(f"EP{ep:02d} audit fail")
    # 清帧省磁盘（成片已归档，可随时重渲）
    import shutil as _sh
    for _d in ("frames","seq"):
        _sh.rmtree(f"{out}/{_d}",ignore_errors=True)
    print(f"EP{ep:02d} DONE {dur}s 用时{int(time.time()-t0)//60}分钟 → {dst}",flush=True)

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--eps",type=int,nargs="+",required=True)
    ap.add_argument("--engine",default="playwright")
    a=ap.parse_args()
    fails=[]
    for ep in a.eps:
        try: do_ep(ep,a.engine)
        except Exception as e:
            print(f"EP{ep:02d} FAILED: {e}",flush=True); fails.append(ep)
    print(f"\n批量完成, 失败: {fails or '无'}",flush=True)
