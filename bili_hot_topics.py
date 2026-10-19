#!/usr/bin/env python3
"""查询B站搜索API，获取财政史相关话题视频播放量证据"""
import json
import re
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")

KEYWORDS = [
    "汉武帝 盐铁专营",
    "王莽 货币改革",
    "崇祯 财政",
    "和珅 家产",
    "交子 纸币",
    "晋商 票号",
    "宋朝 财政",
    "桑弘羊",
]

def search_bili(kw: str) -> list:
    q = urllib.parse.quote(kw)
    url = (f"https://api.bilibili.com/x/web-interface/search/type"
           f"?search_type=video&order=click&page=1&keyword={q}")
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Referer": "https://www.bilibili.com",
        "Cookie": "buvid3=placeholder",
    })
    with urllib.request.urlopen(req, timeout=20) as resp:
        d = json.loads(resp.read().decode("utf-8"))
    return (d.get("data") or {}).get("result") or []

def fmt_play(n) -> str:
    try:
        n = int(n)
    except (TypeError, ValueError):
        return "?"
    return f"{n/10000:.1f}万" if n >= 10000 else str(n)

out = {}
for kw in KEYWORDS:
    try:
        rows = search_bili(kw)[:5]
    except Exception as e:
        print(f"=== {kw} === ERROR: {e}")
        continue
    print(f"=== {kw} ===")
    items = []
    for v in rows:
        title = re.sub(r"<[^>]+>", "", v.get("title", ""))
        play = fmt_play(v.get("play"))
        danm = v.get("video_review")
        author = v.get("author")
        print(f"  {title} | 播放:{play} | 弹幕/评论:{danm} | UP:{author}")
        items.append({"title": title, "play": play, "raw_play": v.get("play"),
                      "author": author, "bvid": v.get("bvid")})
    out[kw] = items

with open("bili_search_evidence.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print("\nsaved -> bili_search_evidence.json")
