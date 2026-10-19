#!/usr/bin/env python3
"""paper-anim-video 阶段一：解说稿逐块配音（小晓 +8%）+ 时间戳
用法：改下方常量后运行。输出 {PID}_voice.wav（页面整段）与 tim_data.json 汇总。
依赖：edge-tts, ffmpeg/ffprobe。偶发 NoAudioReceived 自动重试。
"""
import asyncio, subprocess, re, json, os, sys

# ==== 常量（按篇修改）====
SCRIPT = "/path/to/第XX篇_解说稿.md"      # 解说稿
OUTDIR = "/path/to/workdir"               # 输出目录
VOICE  = "zh-CN-XiaoxiaoNeural"           # 小晓
RATE   = "+8%"                            # 系列定版语速
GAP    = 0.18                             # 块间气口（秒）
PAGES  = ["P00","P01","P02","P03","P04","P05","P06","P07","P08","P09","P10","P11","P12"]

def sh(c): return subprocess.run(c, capture_output=True, text=True)
def dur(p):
    r = sh(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",p])
    try: return float(r.stdout.strip())
    except: return 0.0

def cw(a):  # 块宽：汉字1 标点0.3 ASCII 0.6
    return sum(0.3 if c in "，。：；、" else (0.6 if (c.isascii() and (c.isalnum() or c==" ")) else 1.0) for c in a)

def split_natural(t):  # 断句只认标点；短碎并入相邻；单块≤24宽
    parts = [p for p in re.split(r'(?<=[，。：；、])', t) if p]
    merged = []
    for ck in parts:
        if merged and (cw(merged[-1]) < 4.5 or cw(ck) < 4.5) and cw(merged[-1]) + cw(ck) <= 24:
            merged[-1] += ck
        else: merged.append(ck)
    return merged

async def synth_page(pid, text):
    chunks = []
    for s in [s for s in re.split(r'(?<=。)', text) if s.strip()]:
        chunks.extend(split_natural(s))
    import edge_tts
    wavs, tim, t = [], [], 0.0
    for i, ck in enumerate(chunks):
        mp3, wav = f"{OUTDIR}/{pid}n_{i}.mp3", f"{OUTDIR}/{pid}n_{i}.wav"
        for _ in range(4):
            await edge_tts.Communicate(ck, VOICE, rate=RATE).save(mp3)
            if dur(mp3) > 0.3: break
        sh(["ffmpeg","-y","-i",mp3,"-ar","24000","-ac","1","-c:a","pcm_s16le",wav])
        d = dur(wav)
        tim.append(dict(text=ck, start=round(t,2), dur=round(d,2)))
        t += d; wavs.append(wav)
        if i < len(chunks)-1:
            g = f"{OUTDIR}/{pid}n_gap_{i}.wav"
            sh(["ffmpeg","-y","-f","lavfi","-i","anullsrc=r=24000:cl=mono","-t",str(GAP),g])
            wavs.append(g); t += GAP
    open(f"{OUTDIR}/{pid}n_list.txt","w").write("\n".join(f"file '{p}'" for p in wavs))
    sh(["ffmpeg","-y","-f","concat","-safe","0","-i",f"{OUTDIR}/{pid}n_list.txt",
        "-ar","24000","-ac","1","-c:a","pcm_s16le",f"{OUTDIR}/{pid}_voice.wav"])
    return tim

async def main():
    raw = open(SCRIPT).read()
    os.makedirs(OUTDIR, exist_ok=True)
    all_tim = {}
    for pid in PAGES:
        m = re.search(rf'## {pid}[^\n]*\n+(.*?)(?=\n## |\Z)', raw, re.S)
        if not m: print(f"[skip] {pid} 未找到"); continue
        text = re.sub(r'\s+', '', m.group(1))
        all_tim[pid] = await synth_page(pid, text)
        print(pid, 'blocks:', len(all_tim[pid]),
              'dur:', round(all_tim[pid][-1]['start']+all_tim[pid][-1]['dur'],2))
    json.dump(all_tim, open(f"{OUTDIR}/tim_data.json","w"), ensure_ascii=False)
    # 拼全篇音轨（aac；wav 拼接避免 mp3 丢帧）
    open(f"{OUTDIR}/vo_concat.txt","w").write(
        "\n".join(f"file '{pid}_voice.wav'" for pid in PAGES if pid in all_tim))
    sh(["ffmpeg","-y","-f","concat","-safe","0","-i",f"{OUTDIR}/vo_concat.txt",
        "-c:a","aac","-b:a","128k",f"{OUTDIR}/voice_full.m4a"])
    print("done →", OUTDIR)

asyncio.run(main())
