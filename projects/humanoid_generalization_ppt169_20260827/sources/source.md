# 人形机器人通用泛化最前沿 — 数据源文档（2026-08-27 采集）

## 核心叙事
2026 年最大范式转变：VLA（视觉-语言-行动）→ WAM（世界-行动模型）。"VLAs are dead, long live World Action Models"（Jim Fan）。

## 一、范式转变：VLA → WAM

### VLA 旧范式的根本缺陷
- VLM 骨干学的是"描述世界"，不是"预测世界怎么变"
- 缺动力学模型 → 任务依赖预测场景变化时失效
- 需要近乎相同的任务演示，数据采集贵

### WAM 新范式（NVIDIA 论文《World Action Models are Zero-shot Policies》）
- 视频世界模型当骨架，天生有物理先验
- 三优势：① 吃杂食数据（任何交互数据都能教物理）② 开放世界泛化（物理比语义通用——物体下落方式不随物体变）③ 少样本适配新机体
- 联合预测视频+动作：输出动作同时输出"执行后相机看到什么"——边想象边行动

## 二、NVIDIA Cosmos 3：当前最强开源世界基座（GTC 台北/COMPUTEX 发布）

### 架构：Mixture-of-Transformers 双塔
- 推理塔：自回归 transformer，语言/多模态理解（先想）
- 生成塔：扩散 transformer，图像/视频/音频/动作（后动）
- 三档：Edge 4B（Jetson Thor 15Hz 实时）/ Nano 16B（RTX PRO 6000）/ Super 64B（数据中心）

### 训练数据
- 7.67 亿图像 + 3.48 亿真实世界动态视频 + 800 万动作样本
- 涵盖机械臂操作/自动驾驶/自我中心运动
- 合成数据五大类：物理交互场景/机器人场景/驾驶/数字人/仓储

### 泛化实证
- 对照实验（同数据同算力）：全模态检查点出发的 DROID 策略 RoboLab 28.1%→36.8%（+8.7pp 纯架构先验收益）
- 排行榜：Physics-IQ / R-Bench / PAI-Bench / RoboLab 开源第一；Artificial Analysis 文生图/图生视频（无音频）开源第一
- Cosmos3-Nano-Policy-DROID（16B）/ Edge-Policy-DROID（4B）开源可商用

### 空间理解专项训练（SFT）
- 空间 QA：图像指涉（指向目标/自由空间）、机器人空间 QA（放置点预测、二元相对位置、**自我/世界/物体三参照系可达性判断**）、跨视角对应、透视替换
- Action-CoT：grounding 点→移动推理→2D 航点的结构化推理链（Qwen3-VL-72B 生成推理 + Molmo-7B 定位）

### CVPR 2026 全家桶（2026-06-01）
- Cosmos 3（双塔：Nano 8B+8B / Super 32B+32B——注：chatforest 称两塔参数）
- GR00T N1.6 / Alpamayo 2 Super（32B 自动驾驶推理 VLA）/ OpenShell 沙箱 / NemoClaw 本地部署蓝图 / Physical AI Skills 技能库（github.com/NVIDIA/skills）

## 三、GR00T N 系列进化线（人形专用）

| 版本 | 时间 | 升级 |
|---|---|---|
| N1 | 2025-03 | 首个开放人形基座；双系统：System2 VLM 10Hz 慢思考 + System1 DiT 120Hz 快反射（Kahneman 认知启发）|
| N1.5 | 2025-05 | FLARE 目标函数（人类第一人称视频学习）；GR00T-Dreams 合成蓝图；Eagle 2.5 grounding |
| N1.6 | 2025-12-15 | DiT 32 层（N1.5 两倍）；取消 post-VLM 适配器改为解冻 VLM 顶 4 层；状态相对动作块（更平滑）；全身控制（行走+操作）；数据加 Unitree G1/Agibot Genie1/双臂 YAM/Galaxea R1 Pro；预训练 30 万步 batch 16384 |
| N1.7 | 2026-04-17 | Cosmos-Reason2-2B（Qwen3-VL）骨干；EgoScale：20,854 小时人类第一人称视频（20+ 任务类）——**首个机器人灵巧性缩放律：1k→20k 小时任务完成率翻倍以上** |

## 四、三巨头对比

| 维度 | GR00T N1.6/N1.7 | Gemini Robotics 1.5/ER | π0/π0.5/π0.7 |
|---|---|---|---|
| 骨干 | Cosmos Reason VLM + 32 层 DiT | Gemini 多模态 LLM | PaliGemma 3B + 流匹配 |
| 动作机制 | 扩散（DiT 去噪）| 自回归 token | 流匹配双专家（VLM 专家+动作专家共享注意力）|
| 数据 | 2 万小时人类视频+遥操作+Isaac 合成 | Motion Transfer 统一异构平台数据 | 多平台灵巧操作+DCP（示范/纠正/自主经验）|
| 开放 | 全开源商业许可 | API + On-Device（50-100 演示微调）| OpenPI 开放研究检查点 |
| 特色 | EgoScale 缩放律/跨机体/仿真生态 | 与波士顿动力合作仪器读数（仪表/视镜）| π0.7 组合泛化（2026-04-16）：不同情境技能组合解决未训练任务；叠衣/滤芯/纸箱吞吐翻倍 |

## 五、Sim2Real 空间随机化关键实证（arXiv 2603.22876）

- 系统实验：VLA 灵巧操作的 Sim2Real 泛化
- **空间域随机化（物体位置/朝向/布局）是鲁棒性主导因素**
- 外观随机化（纹理/光照）仅辅助
- → 泛化瓶颈在几何/空间理解，不在视觉外观

## 六、Figure 03（2026 发布）：硬件层泛化补丁

- 掌内嵌入式摄像头：主相机遮挡时（伸进橱柜/狭窄空间）保持近距视觉冗余
- 指尖触觉：3 克力敏（感受纸上回形针重量级）——区分"握稳 vs 将滑"，提前于发生
- 为 Helix VLA 打造；家用安全设计+量产就绪
- 启示：视觉空间+力觉空间融合 = 空间泛化的新硬件补丁

## 七、其他要点
- World Labs R2S2R：真实→仿真→真实训练引擎（Marble 世界重建+海量策略训练+回部署）
- RoboArena 评 Cosmos 3 策略为最佳
- Isaac Lab-Arena：规模化泛化评测框架；OSMO 流水线编排
- LeRobotDataset 格式成社区标准

## 检索记录
- web_search ×3：humanoid generalization foundation / robot manipulation world model VLA sim2real / GR00T N1.5 N1.6 pi0.5 Gemini / Cosmos Alpamayo
- 来源：arXiv 2503.14734（GR00T N1）/2603.22876（Sim2Real）/2606.02800（Cosmos 3 技术报告）；research.nvidia.com（N1.6 官方页）；developer.nvidia.com（WAM 博客/Cosmos 3 博客）；figure.ai（Figure 03）；marktechpost（Top 10 Physical AI 2026）；iotdigitaltwinplm（三巨头对比）；blog.pebblous.ai（架构对比）
