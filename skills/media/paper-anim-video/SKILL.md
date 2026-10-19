---
name: paper-anim-video
description: 论文HTML动画制作：原文加PPT加解说稿出可审看交互动画.
version: 3.0.0
author: yubing
license: MIT
platforms: [macos]
metadata:
  hermes:
    tags: [video, paper, animation, tts, html]
    category: media
    related_skills: [script-to-video, ai-5min-video]
---

# paper-anim-video：论文 → 影院风动态 HTML 动画（当前阶段交付物=动画本体）

**当前任务边界：做 HTML 动画并交老板审看；视频渲染是审看通过后的第二阶段**（文末附渲染命令）。
样板（验收合格的基准）：
- **EP02 BERT（手工精修，老板验收合格）**：`第02期_BERT/动态版工程/bert_anim.html`
- EP04 Scaling Laws P02「样本页」：主视觉舞台四幕式（陡坡→坐标变换拉直→Figure1 复刻→解读）
- 完整 SOP 与踩坑：`论文引擎工程/解说稿直出动画视频_SOP.md`

## 内容三源制（最高军规）
信息源优先级：**论文原文（表意正确性的最终裁判）> PPT（结构提纲）> 解说稿（时间轴）**。
- 每个图表动手前回论文核对 Figure/公式/机制——曲线走向、坐标含义、数量级必须忠于原文
- **PPT 每页 shape 文字零缺失**（逐条收录，不合并不删减；表格行列数字一个不少；公式原样）
- **动态化具象化**：曲线是画出来的、流程走出来的、数字滚动的、对照并排演的——文字卡只做辅助，
  每页要有占屏主视觉；解说念到哪块才出现哪块
- 追光逐句精配：每个配音块→语义对应组件，程序化校验全覆盖零格式错，禁用兜底

## 制作流程（当前阶段：出 HTML 动画 → 老板审看）
```
① python3 scripts/build_project.py --script 第XX篇_解说稿.md --ep N --name 短名 --out 工程目录
   → 小晓+8%配音（自然断句：句尾虚词不悬挂、合并宽28、0.18s气口）+骨架+时间戳
② agent 精修 13 页：每页先回论文定主视觉（参照 EP02 与 EP04-P02 样本），
   再全量收录 PPT 文字、写 rXX(t) 分幕动画、tim.js SPOT 逐句映射
   ★ 先做一页样本交老板审定风格，认可后再铺满
③ 四关质检：bbox 零重叠零溢出（含 SVG 文字不与曲线/轴交叉）+ SPOT 全覆盖校验 + JS 零错误
   + **遮挡专项（普遍性要点）**：按动画极值态复测（卡片-17px上浮/标题滑入/扫光光晕），
   大舞台追光只辉光不位移，帧采样取块起点+0.3s 而非末态
④ 交付：打开 bert_anim.html 给老板审看（←/→ 翻页、空格暂停、数字键直达页）
```

## 第二阶段：审看通过后渲染成片
```
python3 scripts/make_video.py --dir 工程目录 --engine chrome|playwright
   → 动密静疏采样 → 30fps 硬链接展开 → 裁字幕带 → x264+配音 → 成片
python3 scripts/audit_episode.py --video 成片.mp4 --ep N   # 封面/时长/黑页/PPT覆盖四项门禁
成片+工程归档论文文件夹；每集过门禁才做下一集
```

## 画面规范（定版勿改）
- 舞台 1920×1200：上 1080 内容（scale 1.07+下移28px，HUD/页码在字幕带）+ 下 120 字幕带（y1129 基准线）
- 底部 y950 以下干净无文字；无字幕
- 片头：影院扑克25篇统一版加速5s → 本篇海报定格2s → 溶解2s → 毛玻璃标题框整框2s浮现
  （金边呼吸+漂浮不抖，无打字机）→ 鸟群70只整体编队只在框下飞
- 翻页：毛玻璃推入；追光 `.spot` 浮起10px金框（z≥400）；标题框不追光
- 音画同步：页时长=配音实测；rAF 平滑时钟防抖；?t= 定帧冻结过渡

## 关键坑（血泪，勿重复踩）
- ffmpeg concat 时间基 1/25s 吞 30fps 间隔 → 硬链接展开+image2 -framerate 30；seq/ 要一并清
- show() 先存 baseTfm；翻页/追光/漂浮用独立 translate/rotate 属性
- 鸟画布 z200 低于标题框；PAGES 函数名 r00 起（不是 r0）；tim.js 换行符真换行
- 断点续渲会复用改稿前的旧帧——改 HTML 后必须删受影响时段的 frames+seq 再渲
- Chrome CLI 部分沙箱写完截图不退出 → worker 轮询文件+杀进程；Claude 侧用 playwright 引擎
- SPOT 条目必须 [正则,选择器] 二元组——粘连会让整页追光熄灭
- 每页 SVG 文字先算曲线经过区域再定位，杜绝与曲线/轴交叉
- **片头时序是定版、每篇固定、严禁接入配音同步机制**（扑克5s→海报2s→溶解2s→标题框9.2s→鸟群11.2s）
- **P00 是批量改写的豁免区**：任何全篇性脚本清理（删行/替换/BS 化）前后必跑开篇 5 点帧检查
  （t=3/7/8.9/10.5/13 标题框透明度 = 0/0/0/0~1/1），变了立即回滚
- **开篇永久定版**：每期唯一可变 = ①扑克 TARGET=篇号 ②封面海报图；时间线与动态线逐期原样复用
- **每页追光严格检查**：输出「配音块→命中组件」全量对照表人工核对语义，不只查覆盖率
- 精确同步：组件入场 show(...,BS(页,正则)) 读配音块起点，与 SPOT 追光同源同刻
- 追光=漂浮呼吸(-11↔-17px)+金框双层辉光；SVG/舞台容器必须用 drop-shadow（box-shadow 无效）
- 解说稿随时可能被老板更新——重配音后按新块文本复核全部 SPOT/BS 映射

## Prerequisites
- `terminal` 可用 ffmpeg/ffprobe（homebrew）、Chrome
- Python: `edge-tts`、`playwright`
- 25 篇封面 covers/（样板工程内）
