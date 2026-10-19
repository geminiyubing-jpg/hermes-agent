---
name: script-to-video
description: 解说稿生成讲义并合成横竖两版配音字幕视频.
version: 1.0.0
author: yubing
license: MIT
platforms: [macos]
metadata:
  hermes:
    tags: [ppt, video, tts, html]
    category: media
---

# script-to-video：解说词 → PPTX + HTML 讲义 → 配音字幕视频

全链路四阶段。输入一份逐页解说稿（`## 第N页` + `【画面】`/`【口播】`），
输出可编辑 PPTX、可演示 HTML、横竖两版配音字幕 MP4。

## 在 hermes 中使用

1. 用 `read_file` 读逐页稿，确认格式（`## 第N页`、`【口播】`块齐全）
2. 把 `scripts/make_narration.py` 拷到工作目录，改顶部 `SRC/BASE/OUT` 常量，
   用 `terminal` 运行 → 得到 `oral.json` + 每页整段配音
3. 阶段二/三（PPTX 与 HTML）按下方规范手作，内容大纲从逐页稿【画面】转写；
   PPTX 可参考 `scripts/gen_pptx_template.py` 的组件化 helper 写法
4. 把 `scripts/make_video2.py` 拷到工作目录，改 `BASE/HTML` 常量，用 `terminal`
   运行（**先 cd 到工作目录**）：`python make_video2.py both`（或 land/port）

## 阶段要点

### 一、解析逐页稿
- 正则按 `## 第(\d+)页` 切块取 `【口播】` → `oral.json`
- 【画面】人工转写为每页标题 + 卡片/时间轴/要点结构

### 二、PPTX（python-pptx 1.0.2）
- **组件化 helper 先行**（text/shape/card/cardrow/timeline/coin/bullets/bigstat），
  每页只做组装调用——这是可复用的关键
- 设计系统（暗夜鎏金，可整体换肤）：BG #0a0d14 / 金 #ffc94d / 纯白正文 / 珊瑚红
- 中文字体必须同时写拉丁+东亚字形（`<a:ea>`），否则 WPS/Keynote 回退默认字体
- 字符串内引号一律用中文引号，ASCII 双引号会截断 Python 字符串

### 三、HTML 讲义（单文件零依赖，与 PPTX 同视觉系统）
- `.slide` 堆叠 + `.active` 切换；**入场动画用 transition 驱动**
  （`.fx-up{opacity:0}` → `.active .fx-up{opacity:1}` + transition-delay 错峰），
  不要用 animation+fill——transition 方案每次进页重播且不卡透明态
- 3D 浮现：卡片 perspective+rotateX 入场，2.6s 后 levitate 悬浮呼吸
- 质感层用 JS 注入：四角饰/金粒浮尘/竖排题签/山景 SVG/流动光晕
  （`isolation:isolate` + 负 z-index 压到内容下）
- 交互：点击任意处翻页 + ←→ + F 全屏 + 触摸滑动
- **视频拍摄模式（hash 协议，阶段四依赖）**：
  `#static`（跳过动画）`video`（隐藏 UI）`portrait`（竖版排版）
  `p=N`（直达页）`sub=<urlencoded>`（注入字幕条）

### 系列视觉锁定（王朝的钱袋子，老板指令 2026-09-10）

系列内所有期必须与 EP01 成品完全一致（配色/字体/版式/动画/装饰）。
母版：`/Volumes/DATA/hermes-agent-main/mywork/money_pptx/钱是什么_王朝的钱袋子_EP01.html`
——每期复制母版只改文字，不改任何样式。锁定令牌：底 #0a0d14 / 主金 #ffc94d /
暗金 #c9922f / 珊瑚红 #ff6b5e / 正文 #f7f8fb / 辅文 #98a0b3。
详细规范见 runbook：`/Volumes/DATA/ppt-master-main/projects/qian_ep01_ppt169_20260909/VIDEO_PIPELINE.md`

### 四、配音字幕视频（逐句流水线）
- 口播按 `。？！；` 分句 → edge-tts `zh-CN-YunyangNeural` + `rate +6%`
  （帝王系列同款 Andy 音色与语速，勿改）→ 并发4×重试3，句mp3缓存续跑
  → Chrome headless 逐句截图（字幕已内嵌，横 1920×1080 / 竖 1080×1920）
  → 每句 `loop图+mp3+0.45s尾` ts 段 → concat 成片
- **开场规范（学帝王系列）**：第 1 页口播必须以
  "大家好，我是Andy。<系列名>系列第<N>期，……" 开头；
  风格：短句、硬指标、给梗，结尾金句（如"开局一枚贝壳，结局一串代码"）
- **本机 ffmpeg 无 libass/freetype**：ass/subtitles/drawtext 均不可用，
  字幕必须渲染进截图，不要尝试烧字幕滤镜
- 字幕规范：横版≈36px 底部5.5% 无底板；竖版≈66px 底部7% 圆角毛玻璃底板

## 常见坑（血泪）

- Chrome 截图**必须带 `#static`**，否则动画停在 opacity:0 → 全空页
- 改版重跑只清图：`rm -rf imgs_land imgs_port; rm -f seg_*.ts(N)`
  （配音缓存自动跳过；zsh glob 无匹配会中止命令，用 `(N)`）
- 后台跑流水线**先 cd 到工作目录**，相对路径在错误 cwd 下直接失败
- python-pptx cardrow items 支持 3 元组（accent 缺省 GOLD）

## 产出物清单（EP01 实测）

- `*_EP01.pptx`（20 页，Keynote/WPS 可编辑）
- `*_EP01.html`（20 页，双击全屏演示）
- `*_EP01_横版.mp4` / `*_EP01_竖版.mp4`（约 25 分钟，配音+字幕）
