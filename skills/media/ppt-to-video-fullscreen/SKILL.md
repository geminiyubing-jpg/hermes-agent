---
name: ppt-to-video-fullscreen
description: PPT 满屏版论文视频：PPT 铺满画面、字幕独立底带、无大字遮挡.
version: 1.0.0
author: yubing
license: MIT
platforms: [macos]
metadata:
  hermes:
    tags: [ppt, video, tts, fullscreen]
    category: media
    related_skills: [ppt-to-video]
---

# ppt-to-video-fullscreen：PPT 满屏版论文视频

与 `ppt-to-video`（小窗成熟方案）**并列的独立流程**，共享素材链与 TTS/时间轴管线，
仅画面版式不同。参考工程：`/Volumes/DATA/AI-audit/promo-ep2-fullscreen/`（首发验证）、
`/Volumes/DATA/AI-audit/promo-ep6-fullscreen/`（**最新范式**，2026-09-15 第6篇全片交付）。

## 最新范式要点（ep6 实产验证）

- 满屏版**无需 hero 锚点**：build_timeline 的 SEG 直接用口播稿标题生成章节、锚点留空
  （`SEG = [(pid, 章节名, []), ...]` 从 `## P0N 标题` 正则批量生成）
- PPT 模板已全库统一极光深色（2026-09-15 批量修复：浅色→深色 RGBColor 映射、渐变底→纯深底、
  深字→浅字、编号错位修正；原件备份 /tmp/ppt-bak）——若新增 PPT 模板不一致，用同套脚本修复
- 低占用渲染：`--concurrency=3`（约 60 分钟/17 分钟片），机器可同时他用
- 成片命名：`AI顶级前沿论文深刻解读_第NN篇<主题>_满屏横版_YYYYMMDD.mp4`，拷回待发布目录

## 触发规则

用户说「PPT 满屏 / 占满窗口 / 不要小窗」时用本 skill；说「小窗」或未指明时用
`ppt-to-video`。两套互不影响、各自独立演进。

## 与小窗版的差异（仅此 4 点）

| 项 | 小窗版 ppt-to-video | 满屏版（本 skill） |
|---|---|---|
| PPT 卡 | 880×495 左侧卡 | **1778×1000 铺满上部**（960×540 × 1.8519，左右各留 71px） |
| hero 大字 | 有（锚定口播砸落） | **无**（不遮 PPT） |
| 字幕 | y880 叠在画面上（不碰卡） | **底部独立带 y1000–1080**（38–40px，深色底） |
| 章节 chip/页码 | 画面顶部 | 移到字幕带左右两端（24px 小字） |

不变项：封面 3 秒开场（配音 0s 起、封面期无字幕）、小晓 +8% 配音、文字框
逐个入场（HTML 状态截图交叉淡化）、3D 翻页换页、念到哪框亮哪框、无推近缩放、
标点智能断句字幕、卡拉OK标点随前词变色、shrink-to-fit 文字不丢、无 BGM、横屏。

## 实现要点

- 布局表：`src/full/layout.ts` 的 `FULLSCREEN`（slide: left 71, top 0, w 1778, h 1000；caption: top 1016）
- 关 hero：`Segment.tsx` 中 `L.heroW === 0 ? [] : HEROES[pid]`——满屏布局 heroW=0 即全关
- 其余组件与小窗版同源；模板从小窗工程复制后仅改 layout.ts 与两处 import
- 素材链（口播稿/封面/PPT 定位、TTS、时间轴、状态截图、校验、坑）全部见 `ppt-to-video` SKILL.md，本 skill 不重复维护

## 在 hermes / 飞书端使用

同 ppt-to-video 五步（拷脚本→terminal 跑→复制满屏工程骨架→渲→upload），
工程骨架从 `/Volumes/DATA/AI-audit/promo-ep2-fullscreen/` 取。样片先行规则相同。
