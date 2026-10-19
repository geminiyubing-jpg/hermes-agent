---
name: ai-5min-video
description: 讲解稿到PPT再到配音字幕视频的五分钟短视频全流程.
version: 1.0.0
author: yubing
license: MIT
platforms: [macos]
metadata:
  hermes:
    tags: [video, ppt, tts, short-video]
    category: media
---

# ai-5min-video：讲解稿 → PPT → 配音视频（5 分钟短视频）

适合每期 5 分钟、10 段 × 30 秒的系列短视频（AI演化论模式）。
与 script-to-video（HTML 拍摄路线）互补，本技能是 **PPT 直出路线**。

## 输入格式

讲解稿每段格式（AI演化论审阅版即此格式）：

```
【N|30秒|画面提示】
该段解说词……
```

## 全流程四步

### 1. PPTX 制作（4:3 满版）

- 模板：`scripts/gen_pptx_template.py`（python-pptx，AI演化论 EP01 成品生成器）
- 设计铁律（2026 最佳实践）：
  - **一页一观点**，行动式标题（结论写进标题）
  - **每页一个超大焦点**（76–150pt：大数字/金句），其余全部退后
  - **60-30-10**：60% 深空底 / 30% 白字 / 10% 电光青
  - **无边框**、淡填充慎用；留白 30–40%；每页 ≤7 行
  - 统一左网格（0.75in），顶部对齐，**底部 1.6in 留字幕区**（内容止于 5.9in）
  - 中文字体双写 `<a:ea>`；字符串内引号用中文引号
- 色板：底 #0A0E1A / 青 #4DD8FF / 暗青 #2E8FB8 / 紫罗兰 #A78BFA /
  白 #F5F8FF / 灰 #8E9CB5 / 珊瑚 #FF6B5E

### 2. PPT → 高清图

```bash
soffice --headless --convert-to pdf --outdir <dir> <pptx>   # 必须先 cd 到 pptx 目录
pdftoppm -png -r 144 <pdf> <dir>/slide    # 4:3 → 1440×1080
```

### 3. 配音视频合成

`scripts/make_ppt_video.py`（改 BASE/SCRIPT 常量后用 `terminal` 运行）：

- 按标记位切分十段 → `。？！；` 分句 → edge-tts 逐句配音
- **语速校准公式**（实测）：Yunyang 基准 ≈228字/分；
  `+14% ≈ 260字/分`，`+41% ≈ 321字/分`，`+6% ≈ 242字/分`。
  要其他字速：rate = (目标/228 - 1) × 100%
- 字幕：PIL 绘制，**单行贴最底**（48px 起，超长自动缩到 24px，白字深影居中）
  ——本机 ffmpeg 无 libass/drawtext，禁止尝试烧字幕滤镜
- 每句 `loop图+mp3+0.45s尾` → ts 段 → concat `-c copy` + faststart

### 4. 发布

看板任务派发或飞书直发，归「AI资讯快递」合集、按 project_video_archive 归档（合集名已由AI演化论更名，2026-09-10 老板指令）。

## 常见坑（血泪）

- **后台/脚本执行必须 cd 到工作目录**——用绝对路径 wrapper（参考
  `mywork/ai_ep01/run.sh`），否则相对路径全部失败
- 讲解稿标记正则：排除类要用 `[^】\n]`，**不能写 `[^\]]`**（中文】不是]，
  贪婪匹配会吞整篇）
- PIL 中文字体路径：`/System/Library/Fonts/Supplemental/Songti.ttc`
  （PingFang.ttc 不在默认路径）
- 改语速要 `rm -rf vid/sent vid/imgs; rm -f vid/seg*.ts(N)` 全清重跑
  （配音有缓存会跳过导致新旧混速）
- zsh 删文件 glob 无匹配会中止命令：`rm -f seg*.ts(N)`

## 产出物（EP01 实测）

- `*_4x3.pptx`（10 页满版，可编辑）
- `*_4x3_配音版.mp4`（4:3 · 约5分钟 · 55 句 · 单行贴底字幕 · 260字/分）
