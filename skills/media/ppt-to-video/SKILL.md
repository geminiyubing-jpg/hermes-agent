---
name: ppt-to-video
description: PPT 加解说稿全自动合成宣传片式横屏配音视频.
version: 1.0.0
author: yubing
license: MIT
platforms: [macos]
metadata:
  hermes:
    tags: [ppt, video, tts, html]
    category: media
    related_skills: [script-to-video]
---

# ppt-to-video：PPT + 解说稿 → 横屏配音视频

已验证全流程（参考工程 `/Volumes/DATA/AI-audit/promo-mit-brain/`）。输入 PPTX +
按页拆好的解说词，输出宣传片式横屏 MP4：文字框逐个上浮入场、3D 翻页换页、
相机缓推、口播锚定大字砸落、词级卡拉OK字幕。

## 固定偏好（用户已选定，不要再问）

- 画幅：横屏 1920×1080，只渲无 BGM 版（保留人声+音效）
- 配音：edge-tts zh-CN-XiaoxiaoNeural（小晓）+8%
- 特效：文字框上浮淡入 / 换页 3D 翻页 / Ken Burns 缓推 / hero 砸落锚口播 / 卡拉OK字幕
- **开场（2026-09-14 定稿）**：0-3 秒全屏 16:9 封面图，配音 0 秒即开始，封面期不显示字幕；第 3 秒起进 P01 画面+字幕（时间轴 PAD_HEAD=0.1，Caption 在全局前 90 帧隐藏）

## 素材定位（每集自己去目录找，不要问用户）

- 发布排期：`/Volumes/DATA/AI论文PPT_20260914交付/发布顺序总表_v2_影响力定稿.md`
- 每集真相源目录：`/Volumes/DATA/作品总库/B号今天也知道了_新号/AI顶级前沿论文深刻解读/AI顶级前沿论文深刻解读-第NN篇<主题>_YYYYMMDD_待发布/`
  - 口播稿 = 该目录下 `AI论文解读-第NN篇_口播稿.md`（以最新修改为准，优先于交付目录的解说词_优化版）
  - 封面图 = 该目录 `封面/sNN_16x9宽幅.jpg`
  - PPT = 该目录 .pptx（与交付目录同名）
- 工程骨架：参考 `/Volumes/DATA/AI-audit/promo-ep3-gpt3/`（最新范式：含封面开场）

## 流程（样片先行，2026-09-14 定稿）

新集先渲 **1 分钟样片**（`--frames=0-2100`）交用户确认，通过后再渲完整版；完整版约 20 分钟（--concurrency=11）。

## 触发规则（强制）

**凡论文解读/论文解构类视频任务，一律用本 skill**（用户 2026-09-13 指定），不要走
script-to-video 或其他视频流程；固定偏好直接生效，不询问用户选特效/音色/画幅。

## 在 hermes / 飞书端使用

用户在飞书发 PPT 附件 + 解说词（或要求从 PPT 文本起草解说词）：

1. 下载附件到工作目录，用 `read_file` 核对解说词是否按页分段
2. 把 `scripts/` 五个脚本拷到工作目录，改顶部路径常量，用 `terminal` 依次运行：
   `gen_tts.py`（配音+词级时间戳）→ `build_full_timeline.py`（时间轴）；
   新 PPT 先跑 `extract_ppt_html.py` → `gen_slides_html.py` → Playwright 批量截图状态图
3. Remotion 工程从参考工程复制骨架，替换 timeline.json / slides-states / voice-full，
   `terminal` 渲染（`npx remotion render src/entry.tsx Full16x9 out/<name>.mp4 --concurrency=11`）
4. 产物 `upload` 回飞书
5. 用户要剪映换声时：渲 plate 干净底片后跑 `gen_jianying_draft.py` 建草稿

## 六步要点

1. 解说词按页拆 P01…PNN 写入 `gen_tts.py` 的 SEGMENTS；数字读法转汉字（"4.3倍"→"四点三倍"），希腊字母 τ 拒收需转写
2. TTS 必须显式 `boundary="WordBoundary"`（默认只有句级）；偶发 NoAudioReceived 用重试
3. 时间轴脚本生成禁手敲：段起点 0.5s 头 +0.7s 间距、字幕行 ≤13 字、hero 锚点=词流短语匹配
4. PPT→HTML：递归展开组合形状、保持文档 z 序、填充 alpha 从 XML 读；文本框带 t<k> class + `?n=` 状态脚本；Playwright 2x 截全部状态
5. 验收：HTML 截图 vs LibreOffice 导出原 PPT PNG，逐页行布局相关性 ≥0.9
6. 渲染约 13 分钟/15 分钟片（逐帧 Chromium 截图本质）

## 已踩坑（必读）

- 不要在 Remotion 里 DOM 重建 PPT——字号换算必出错且垫截图会重影；唯一稳路线 = HTML 状态截图序列 + 交叉淡化
- 字幕行尾 0.15s 余量，剪映导出必须钳到下一行 t0（SegmentOverlap）
- zsh 后台命令里删除无匹配通配符会中止整链
- 对比验收要同缩放（Ken Burns 会把相关性 0.94 砸成 0.4，是假象）

## Prerequisites

- `terminal` 可用；edge-tts（uv tool）、python-pptx、Playwright、Remotion 工程骨架
- 素材授权见参考工程 sources.md
