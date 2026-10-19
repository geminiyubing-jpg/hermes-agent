# 具身智能与空间智能前沿 — 数据源文档（2026-08-27 采集）

## 核心命题（用户直觉，已被前沿研究证实为显学）
LLM 与具身三维空间感知可能不同源；动物无语言文字但有完备空间认知；空间能力比语言知识更本源；具身泛化需要研究比 LLM 更本源的技能认识。

## 一、支持"空间智能更本源"的三大证据

### 1. Apple SPACE 基准（arXiv 2410.06468）
- 基于几十年动物认知研究设计（大小尺度空间认知：地图绘制/距离方向估计/抄近路 + 心理旋转/视角切换/迷宫补全/明尼苏达形状板）
- 结果：前沿模型大尺度任务接近随机；心理旋转、视角获取、迷宫、形状板等经典动物测试 near chance
- 最狠结论："没有任何生物智能表现出如此先进的高级认知同时在基本空间认知上失败得如此彻底"
- "生物智能中空间认知是高级认知的前提，空间障碍是高级疾病诊断指标"——前沿模型把顺序倒过来了
- 开放问题：空间缺陷是否因果性导致高级任务失败？embodiment 是否必要？

### 2. 脚手架倒置论文（arXiv 2607.13560 Grounded world models in biological organisms and future embodied AI）
- 当前 AI：语言规律当脚手架，其他模态往上挂
- 生物智能：交互获得的落地世界模型是语义脚手架，语言挂上去
- 五个生物神经回路案例：物理/概念空间导航、affordance 感知与交互、主动感知与探索学习、稳态控制与情绪、自我/世界区分
- 生物智能四特征（当前 AI 全缺）：内在动力学为基础、行动为中心对齐、自主经验开放学习（vs 被动喂数据）、早期预测控制为高级认知搭台

### 3. 皇家学会导航工具箱（Proc R Soc B 2023.1304，2026 持续更新）
- 跨物种层级：感觉输入→路标→路线→认知地图（度量内部模型）→符号（语言/地图/蜜蜂摇摆舞）
- 大鼠蝙蝠鸽子乌鸦狗大象都有前四层——无语言有认知地图
- 蜜蜂摇摆舞=前语言符号系统
- 层级双向反馈（高层影响低层）
- 认知地图 vs 认知图（graph）之争：拓扑关系+局部度量

## 二、四条世界前沿路线

### 路线①：抽象潜空间派（JEPA）— LeCun / AMI Labs
- 2025-11 LeCun 离开 Meta；2026-03-09 AMI Labs 融资 10.3 亿美元（35 亿估值，欧洲史上最大种子轮）
- 主张："LLM 是统计幻觉"（A statistical illusion. Impressive, yes. Intelligent, no.）
- JEPA：不预测像素/token，在抽象嵌入空间预测未来状态；只学行动相关结构，丢弃噪声
- 发布节奏：I-JEPA 2023 → V-JEPA 2024 → V-JEPA 2 2025-06 → V-JEPA 2.1 2026-03（年均一版）
- LeJEPA（2026）：可证明的理论——SIGReg 高斯正则防坍塌，无需启发式
- When Does LeJEPA Learn a World Model?（2026-05）：证明能从非线性观测线性恢复隐世界变量（平稳加噪转移类世界）
- LeWorldModel（arXiv 2603.19312）：首个从原始像素端到端稳定训练的 JEPA，15M 参数单卡数小时收敛
- 96 家初创基于世界模型路线做物理 AI

### 路线②：空间智能派（3D 原住民）— 李飞飞 / World Labs
- 融资 10 亿美元（NVIDIA/AMD/Autodesk 参投）
- 李飞飞原话："The case for us is a 500 million year story — animal intelligence starts with seeing and moving in the physical world"
- Marble：首个商用多模态世界模型（文本/图像/视频→可编辑持久 3D 世界），2025-09 预览、11 月 GA，$20/月起
- 2026-07-21 收购 SceniX；R2S2R（real-to-sim-to-real）机器人训练引擎
- 2026-07-28 访谈："训练机器人不像训练 LLM"；模拟层解锁下一代机器人

### 路线③：脑启发认知地图派 — BSC-Nav（Nature Communications 2026-08）
- 诊断：MLLM 具身代理"反应式、无状态"，缺结构化空间记忆
- 方案：生物三层空间知识——路标记忆（线索-位置绑定）+ 认知地图（自我中心轨迹→体素化→非自我中心地图）+ 工作记忆（动态检索对齐语义目标）
- 与基础模型接口：DINOv2 做感知接地，GPT-4V 做语义解释（MLLM 是工程模块，空间记忆是计算接口）
- 战绩：实例级导航 SPL 17.6%→44.9%；零样本长程指令跟随 42.7%→53.1%；VLN-CE 零样本 38.5% SR（距监督 SOTA 8.5%）；OpenEQA 54.6 LLM-Match
- 局限自述：非认知忠实模型；理论贡献仍是架构性的

### 路线④：心理导航派 — NavMind / Video2Mental（arXiv 2603.21577）
- Video2Mental 基准：23,700 高难样本；从长自我中心视频建分层认知地图+路标路径规划，模拟器物理验证
- 发现：心理导航不自然涌现——前沿模型 SR 3.76-5.54%，Landmark IoU <5%，F1 <35%；即使给真值地图规划仍错——瓶颈在结构化空间推理非感知
- NavMind：显式细粒度认知地图作为可学习中间表示；难度分层渐进 SFT（拒绝采样滤简单样本）；基于 Qwen3-VL
- CVPR 2026 LASAR：双记忆（情景+语义认知地图）+ ST-CRL 对比目标；VSI-Bench 零样本 +3.5%
- 鸽子启发（2606.02459）：动态认知地图参数化场景布局 + 空间断言代码 SAC 提供密集奖励；MindCube 80.5%（ROTATION 子集超 SOTA 29.5 分）

## 三、四派共识与分歧
共识：具身泛化需要行动中获得的空间结构；预测-行动-地图是前语言内核；语言当接口不当骨架
分歧：纯 JEPA（去语言化）vs 双系统（空间底座+语言接口）vs 生成式世界模型（Sora/Genie 路线：视觉生成/下一帧预测——暴露偏差问题：训练看高清、推理吃自己生成的残次品，误差滚雪球）
四营会战：视觉生成派（Sora/Veo）、下一帧预测派（Genie/Gaia-1）、抽象潜空间派（JEPA/DreamerV3/AMI）、3D空间物理派（World Labs/物理引擎）

## 四、检索记录
- web_search ×3：embodied spatial cognition without language / JEPA LeCun world model 2026 / World Labs Fei-Fei Li Marble
- 来源：arXiv 2410.06468 / 2607.13560 / 2603.21577 / 2603.19312 / 2606.02459；Nature Communications 2026（BSC-Nav）；Proc R Soc B（导航工具箱）；CVPR 2026（LASAR）；worldlabs.ai；aiautomationglobal；turingpost；latent.space；chipstrat（Bloomberg 访谈）
