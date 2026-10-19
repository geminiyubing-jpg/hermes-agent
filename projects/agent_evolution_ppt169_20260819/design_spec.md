# Agent 演进史培训 - Design Spec

> 人类可读设计叙事。机器可读执行契约见 `spec_lock.md`（Executor 每页前重读）。

## I. Project Information

| Item | Value |
| ---- | ----- |
| **Project Name** | agent_evolution |
| **Canvas Format** | PPT 16:9 (1280×720) |
| **Page Count** | 15 |
| **Design Style** | A) General Versatile + 深色科技风（dark tech） |
| **Target Audience** | 银行内审团队 + 技术爱好者混合层（懂业务不写代码） |
| **Use Case** | 内部培训：Agent 演进史 + 2026 前沿 + 启示 |
| **Created Date** | 2026-08-19 |

## II. Canvas Specification

| Property | Value |
| -------- | ----- |
| **Format** | PPT 16:9 |
| **Dimensions** | 1280×720 |
| **viewBox** | `0 0 1280 720` |
| **Margins** | 左右 60px，上下 48px |
| **Content Area** | 1160×624（安全区） |

## III. Visual Theme

### Theme Style

- **Style**: 深色科技风——深空蓝底、电光青主色、琥珀橙强调，配时间轴/层级图
- **Theme**: Dark theme
- **Tone**: 科技、前沿、专业但不冰冷

### Color Scheme

| Role | HEX | Purpose |
| ---- | --- | ------- |
| **Background** | `#0B1426` | 页面深空蓝底 |
| **Secondary bg** | `#111F35` | 卡片底色 |
| **Primary** | `#22D3EE` | 电光青——标题装饰、图标、关键结构 |
| **Accent** | `#F59E0B` | 琥珀橙——数据高亮、关键转折 |
| **Secondary accent** | `#8B5CF6` | 紫——阶段二/辅助渐变 |
| **Body text** | `#E8EEF7` | 亮白正文 |
| **Secondary text** | `#94A3B8` | 说明文字 |
| **Tertiary text** | `#64748B` | 页脚、注释 |
| **Border/divider** | `#1E3A5F` | 卡片描边、分隔线 |
| **Success** | `#10B981` | 正向指标 |
| **Warning** | `#EF4444` | 风险标记 |

### AI Image Strategy

- **Image Rendering**: blueprint（技术蓝图风——网格、单色 cue、工程感，与深色科技底天然契合）
- **Image Palette**: tech-neon（深底 + 电青主导 + 橙强调，与 §III HEX 完全同源）

### Gradient Scheme

```xml
<linearGradient id="titleGradient" x1="0%" y1="0%" x2="100%" y2="0%">
  <stop offset="0%" stop-color="#22D3EE"/>
  <stop offset="100%" stop-color="#8B5CF6"/>
</linearGradient>
<radialGradient id="bgDecor" cx="80%" cy="20%" r="50%">
  <stop offset="0%" stop-color="#22D3EE" stop-opacity="0.12"/>
  <stop offset="100%" stop-color="#22D3EE" stop-opacity="0"/>
</radialGradient>
<linearGradient id="scrimLeft" x1="0%" y1="0%" x2="100%" y2="0%">
  <stop offset="0%" stop-color="#0B1426" stop-opacity="0.92"/>
  <stop offset="60%" stop-color="#0B1426" stop-opacity="0.55"/>
  <100% offset="100%" stop-color="#0B1426" stop-opacity="0.12"/>
</linearGradient>
```

## IV. Typography System

### Font Plan

**Typography direction**: 现代 CJK 黑体系（深色科技风标准）

| Role | Chinese | English | Fallback tail |
| ---- | ------- | ------- | ------------- |
| **Title** | `"Microsoft YaHei", "PingFang SC"` | `Arial` | `sans-serif` |
| **Body** | `"Microsoft YaHei", "PingFang SC"` | `Arial` | `sans-serif` |
| **Emphasis** | `"Microsoft YaHei", "PingFang SC"` | `Arial` | `sans-serif` |
| **Code** | — | `Consolas, "Courier New"` | `monospace` |

**Per-role font stacks**:

- Title: `"Microsoft YaHei", "PingFang SC", Arial, sans-serif`
- Body: `"Microsoft YaHei", "PingFang SC", Arial, sans-serif`
- Emphasis: same as Body
- Code: `Consolas, "Courier New", monospace`

### Font Size Hierarchy

**Baseline**: Body = 18px（内容密——培训页信息量大）

| Purpose | Ratio | @18px | Weight |
| ------- | ----- | ----- | ------ |
| Cover title | 3.3x | 60px | Bold |
| Chapter opener | 2.2x | 40px | Bold |
| Page title | 1.7x | 30px | Bold |
| Hero number | 1.8x | 32px | Bold |
| Subtitle | 1.25x | 22px | SemiBold |
| **Body** | **1x** | **18px** | Regular |
| Annotation | 0.78x | 14px | Regular |
| Page number | 0.61x | 11px | Regular |

## V. Layout Principles

### Page Structure

- **Header area**: y 48-100（页标题 + 编号徽章）
- **Content area**: y 110-660（主内容区）
- **Footer area**: y 680-712（页码 + 培训名）

### Layout Pattern Library

| Pattern | 用于 |
| ------- | ---- |
| Full-bleed + floating text | P01 封面、P14 尾页 |
| Horizontal timeline | P03 前史三源头 |
| Center-radiating | P04 ReAct 骨架 |
| Three-column cards | P06 多智能体 |
| Layered pyramid | P07 能力分层 |
| Four-quadrant | P09 2026 前沿全景 |
| Asymmetric split (3:7) | P05 记忆与规划、P10-12 前沿主线 |
| Z-pattern | P08 2025 商业化 |
| Negative-space | P13 三判断 |

### Spacing Specification

**Universal**: 安全边距 48-60px；内容块间距 28px；图标-文字间距 10px

**Card-based**: 卡片间距 24px；卡片内边距 24px；圆角 12px；双行卡高 270px；三列卡宽 368px

**Non-card**: 行高 1.5；全出血文字须配 scrim 渐变

## VI. Icon Usage Specification

### Source

- **Built-in icon library**: `templates/icons/tabler-outline`（线性图标与蓝图风最搭）
- **Usage**: `<use data-icon="tabler-outline/<name>" .../>`
- **Stroke width**: 2（deck 全局锁定）

### Recommended Icon List

| Purpose | Icon Path | Page |
| ------- | --------- | ---- |
| 规则系统 | `tabler-outline/settings` | P03 |
| 反应式 | `tabler-outline/bolt` | P03 |
| RL | `tabler-outline/target` | P03 |
| 循环推理 | `tabler-outline/refresh` | P04 |
| 工具调用 | `tabler-outline/tool` | P04 |
| 技能库 | `tabler-outline/library` | P05 |
| 记忆 | `tabler-outline/database` | P05 |
| 搜索树 | `tabler-outline/hierarchy` | P05 |
| 反思 | `tabler-outline/eye-check` | P05 |
| 多角色 | `tabler-outline/users` | P06 |
| GUI 操作 | `tabler-outline/device-desktop` | P06 |
| 深度研究 | `tabler-outline/zoom-check` | P06 |
| 协议 | `tabler-outline/plug-connected` | P08 |
| RL 训练 | `tabler-outline/brain` | P10 |
| 算力 | `tabler-outline/cpu` | P11 |
| 记忆底座 | `tabler-outline/database` | P12 |
| 盾牌/安全 | `tabler-outline/shield-check` | P13 |
| 审计 | `tabler-outline/clipboard-check` | P13 |
| 层级 | `tabler-outline/stack-2` | P07 |
| 网络生态 | `tabler-outline/topology-star` | P07 |

## VII. Visualization Reference List

Catalog read: 71 templates

| Page | Template | Path | Summary-quote (verbatim) | Usage |
| ---- | -------- | ---- | ------------------------ | ----- |
| P03 | timeline | `templates/charts/timeline.svg` | "Pick for 3-8 milestone events on a horizontal time axis (no duration). Skip for tasks with start/end ranges (use gantt_chart) or vertical layout (use roadmap_vertical)." | 前史三源头里程碑（1956 GPS → 1986 Brooks → 2015 DQN） |
| P07 | pyramid_chart | `templates/charts/pyramid_chart.svg` | "Pick for 3-6 stratified hierarchy layers in flat 2D side-view — Maslow's hierarchy, maturity models, value hierarchy, capability tiers, market segments, audience pyramid. Skip for dramatic tone (use pyramid_isometric), flat priority list (use vertical_list), or org reporting (use top_down_tree)." | L0-L5 能力分层金字塔 |
| P09 | quadrant_text_bullets | `templates/charts/quadrant_text_bullets.svg` | "Pick for any 2×2 framework where each quadrant holds a titled bullet list — SWOT (Strengths/Weaknesses/Opportunities/Threats, internal-external × helpful-harmful), Ansoff (Existing/New Markets × Existing/New Products), or any named two-axis matrix with text content. Skip for items plotted as points (use matrix_2x2) or bubble-sized portfolios (use quadrant_bubble_scatter)." | 2026 四主线 2×2 矩阵 |
| P15 | labeled_card | `templates/charts/labeled_card.svg` | "Pick for 3-4 parallel aspects of one subject with per-aspect titles + short body (self-introduction, four-pillar overview, capability..." | 五条关键启示卡片 |

**Runners-up considered**:

- `isometric_stairs` | rejected for P07: 分层模型是严格的概念层级（L0-L5 能力判定），flat 2D 侧视金字塔比等距楼梯的"成长隐喻"更贴切；楼梯适合阶段性成长叙事，此处需要的是判定标准
- `hub_spoke` | rejected for P09: 四主线相互独立、无中心辐射关系，2×2 矩阵的平行结构更符合内容形状
- `roadmap_vertical` | rejected for P03: 前史强调水平时间流动（1956→2015 跨 60 年），横向时间轴与叙事方向一致；垂直路线图适合任务里程碑而非历史流
- `numbered_steps` | rejected for P15: 启示是并列观点而非顺序步骤，labeled_card 的并列卡片更贴切

## VIII. Image Resource List

| Filename | Dimensions | Ratio | Purpose | Type | Layout pattern | Acquire Via | Status | Reference | text_policy | page_role |
| -------- | --------- | ----- | ------- | ---- | -------------- | ----------- | ------ | --------- | ----------- | --------- |
| cover_bg.png | 1280x720 | 1.78 | 封面背景——AI agent 演进的抽象视觉 | Background | #1 full-bleed background with floating title + #29 two-stop scrim | ai | Pending | Abstract evolutionary visualization: a luminous neural pathway ascending from simple geometric nodes at the bottom through increasingly complex network structures toward a radiant constellation at the top; calm dark lower-left region reserved for title overlay | none | hero_page |
| chapter2_bg.png | 1280x720 | 1.78 | P04 章节页背景——LLM 觉醒 | Background | #57 full-bleed texture wash | ai | Pending | Atmosphere of a large language model's interior: vast field of softly glowing interconnected nodes suggesting attention flow, gentle depth, dark and calm enough for text overlay | none | hero_page |
| chapter3_bg.png | 1280x720 | × | P06 章节页背景——多智能体协作 | Background | #57 full-bleed texture wash | ai | Pending | Multiple luminous agent entities exchanging light-streams around a shared central workspace, suggesting collaboration; dark field, low contrast for overlay | none | hero_page |
| chapter4_bg.png | 1280x720 | 1.78 | P10 章节页背景——自进化生态 | Background | #57 full-bleed texture wash | ai | Pending | Self-evolving ecosystem metaphor: neural tree growing recursive branches that bud into smaller copies of themselves, spiral growth suggestion; dark, calm center | none | hero_page |
| memory_grid.png | 640x640 | 1.0 | P05 记忆机制插图 | Illustration | #2 left-third image + right text body | ai | Pending | Memory architecture illustration: layered memory banks with glowing retrieval paths connecting a central agent core to past-experience fragments | none | local |

> Image-as-canvas coverage：本 deck 的图片页为封面 + 3 张章节页（纯 atmosphere backdrop）+ P05 局部插图，无内容型照片页，故不使用 #38-#46 家族——内容页信息由原生 SVG 结构承担，符合 GATE 第 3 条豁免条件（全部为 cover/chapter divider/atmosphere backdrop）。

## IX. Content Outline

### Part 1: 开场

#### Slide 01 - 封面

- **Layout**: Full-bleed 背景图 + 浮动标题
- **Title**: 智能体的进化之路
- **Subtitle**: 从规则引擎到自主智能体——AI Agent 演进史与 2026 前沿
- **Info**: 内部培训 · 2026 年 8 月

#### Slide 02 - 目录

- **Layout**: agenda_list（左侧大编号 + 标题 + 一句话简介）
- **Title**: 今天聊什么
- **Content**: 六部分：前史 / LLM 纪元 / 多智能体与工作流 / 能力分层 / 2026 前沿 / 启示

### Part 2: 前史

#### Slide 03 - Agent 前史：三个源头

- **Layout**: 水平时间轴（timeline 模板改编）
- **Title**: Agent 前史：三条河流的汇合（1950s-2010s）
- **Visualization**: timeline
- **Content**:
  - 符号主义（1956 GPS / 1970s MYCIN）：规则+推理，可解释但脆弱
  - 反应式（1986 Brooks）：感知-行动直连，智能不需要表征
  - 强化学习（1998 Q-learning / 2015 DQN）：奖励驱动，AlphaGo 前夜

### Part 3: LLM Agent 纪元

#### Slide 04 - 章节页：LLM 纪元开启

- **Layout**: 全屏背景图 + 大字
- **Title**: 第二章 · LLM 纪元
- **Subtitle**: 2022-2024：语言模型成为 Agent 的大脑

#### Slide 05 - 奠基三件套与记忆规划

- **Layout**: 不对称分栏（左 3 右 7）
- **Title**: ReAct 骨架 + 记忆与规划的分层
- **Content**:
  - ReAct（2022）：Thought→Action→ Observation 循环，一切现代 agent 的骨架
  - Toolformer：模型自学何时调工具
  - Voyager 技能库：Minecraft 终身学习
  - Generative Agents：记忆流+反思，25 居民涌现社会行为
  - ToT 搜索树、Reflexion 语言强化

### Part 4: 多智能体与工作流工程

#### Slide 06 - 章节页：多智能体与工作流

- **Layout**: 全屏背景图 + 大字
- **Title**: 第三章 · 多智能体与工作流
- **Subtitle**: 2024-2025：从单体到生态

#### Slide 07 - 能力分层模型

- **Layout**: 分层金字塔（pyramid_chart 模板改编）
- **Title**: Agent 能力分层：L0-L5
- **Visualization**: pyramid_chart
- **Content**: L0 聊天助手 / L1 工具调用 / L2 工作流执行 / L3 自主规划 / L4 自进化 / L5 多智能体生态 + 判别问题

#### Slide 08 - 2025 商业化浪潮

- **Layout**: Z-pattern 三块
- **Title**: 2025：从实验室到生产
- **Content**:
  - Deep Research：搜索+综合长任务
  - Computer Use：GUI 操控落地
  - MCP 协议：工具接入标准化
  - Claude Skills：知识包
  - Agent Harness 概念成型

### Part 5: 2026 前沿

#### Slide 09 - 2026 前沿全景

- **Layout**: 2×2 矩阵（quadrant_text_bullets 模板改编）
- **Title**: 2026 前沿：四大主线
- **Visualization**: quadrant_text_bullets
- **Content**: Harness-Native RL / Test-Time 精细化 / 记忆系统成熟 / 可靠性经济学

#### Slide 10 - 章节页：Harness-Native RL

- **Layout**: 全屏背景图 + 大字
- **Title**: 主线一 · Harness-Native Agentic RL
- **Subtitle**: 训练对象从模型变成整个系统

#### Slide 11 - Test-Time Compute 精细化

- **Layout**: 不对称分栏
- **Title**: 算力该花在哪：Verification 吃掉 Sampling
- **Content**: CLR 定向验证 / DCR 发散收敛 / RLVR 难度调度 / 趋势判断

#### Slide 12 - 记忆系统与可靠性

- **Layout**: 双主题并列（上下两块或左右两块）
- **Title**: 记忆成熟 + 可靠性经济学
- **Content**: MELD 协议 / 记忆底座评测 / 反直觉发现 / Fragility / HarnessRisk / ACID 事务 / 行为合同

### Part 6: 收束

#### Slide 13 - 三个判断

- **Layout**: 负空间主导（三个大观点）
- **Title**: 我的三个判断
- **Content**:
  1. Harness 是新的训练边界
  2. 验证 > 生成的算力哲学
  3. 从能力展示到可靠性经济学

#### Slide 14 - 关键启示

- **Layout**: 五卡片（labeled_card 模板改编）
- **Title**: 五条带回家的启示
- **Visualization**: labeled_card
- **Content**: 天花板在 harness / 记忆是基础设施 / 验证比生成值钱 / 可靠性=竞争力 / 生产三问

#### Slide 15 - 尾页

- **Layout**: 全屏背景图 + 居中大字
- **Title**: 谢谢
- **Subtitle**: Q&A · 一起聊聊你身边的 Agent 机会

## X. Speaker Notes Requirements

- 文件命名与 SVG 同名（`01_cover.svg` → `notes/01_cover.md`）
- 每页：讲解要点 + 时间提示 + 过渡句
- 风格：对话式、有钩子（"你每天用的输入法补全，其实就是 L0"）
- 总时长目标：40 分钟（15 页 × ~2.5 分钟）

## XI. Technical Constraints Reminder

### SVG Generation Must Follow:

1. viewBox: `0 0 1280 720`
2. 背景用 `<rect>`
3. 文本换行用 `<tspan>`（禁 `<foreignObject>`）
4. 透明度用 `fill-opacity` / `stroke-opacity`（禁 `rgba()`）
5. 禁：`mask`、`<style>`、`class`、`foreignObject`、`textPath`、`animate*`、`script`
6. 文本字符：原生 Unicode（—、→、©）；XML 保留字转义 `&amp;` `&lt;` `&gt;`
7. `marker` 须在 `<defs>`、`orient="auto"`、形状为三角/菱形/圆
8. `clipPath` 仅用于 `<image>`，单一形状子元素

### PPT Compatibility Rules:

- `<g opacity>` 禁用——在每个子元素上单独设置
- 图片透明用 overlay mask 层
- 仅内联样式；禁外部 CSS 和 `@font-face`
