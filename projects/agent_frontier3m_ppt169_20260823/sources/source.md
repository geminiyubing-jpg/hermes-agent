# AI Agent 前沿论文（2026-06 至 2026-08）— 数据源文档

采集时间：2026-08-23，全部为 arXiv 官方 abstract + 多源交叉验证

## 一、长程任务（The Horizon Gap）——季度定义性论文

### The Horizon Gap（arXiv 2608.06663，2026-08-07）
- 1547 篇 arXiv 论文系统综述（2024-2026），"horizon gap"命名：前沿模型单次前向可解研究级问题，但多小时的 agent 任务仍失败（丢失早期决策、半成品宣称完成、目标漂移）
- 关键概念澄清：long-horizon（任务属性）≠ long-context（模型属性）≠ long-term memory（系统属性）
- 六类组织：planning/memory/execution/training/evaluation/foundations-safety × 三轴（within-context / beyond-context / cross-task-persistent）
- 核心发现：outcome-only 信号随 horizon 拉长失效；领域回应（PRM、credit assignment、轨迹诊断）都是"制造过程信号"
- GitHub: deepgrounding/long-horizon-task

## 二、训练侧：RL for Agents

### HPO: Hindsight Policy Optimization（arXiv 2607.16257，2026-07）
- 长程交互 RL 的动作贡献区分难 → 高优化方差；HPO 在 intent space 对比当前策略与 hindsight 分布，低方差平滑信号
- 无 critic 稳定 RL 新路径；multi-hop 任务显著提升；offline HPO > online HPO

### MileGPO（arXiv 2608.19803，2026-08）
- 长程 agentic RL credit assignment：Milestone Discovery（成功轨迹找里程碑+失败轨迹找陷阱）+ Reliability-Calibrated Shaping（按结果置信度加权）
- 图策略优化 + 过程级 credit

### Demystifying RL for Long-Horizon Tool-Using Agents / STAR（arXiv 2603.21972）
- TravelPlanner 测试床，5 轴分解（reward shaping/model scaling/data composition/algorithm/env stability）
- 尺度感知配方：小模型需要分阶段课程奖励

### Agent-Omit（ICML 2026，arXiv 2602.04284，HKUST）
- Agentic RL 训练"自适应上下文省略"：学会省略冗余 thought/observation
- 冷启动数据（单轮+多轮省略场景）微调 + RL

### Memory-R2（2026）
- 长程记忆增强 agent 的公平 credit assignment

## 三、记忆侧：ICML 2026 记忆五重奏（mem0 8-12 盘点）

### MemoryArena（arXiv 2602.16313，ICML 2026，14 作者）
- 多会话相互依赖任务评估 gym：记忆与行动耦合（Memory-Agent-Environment loop）
- 核心发现（全场最多引用）：刷爆 LoCoMo 的 agent 在真实多会话任务上失败；LoCoMo 分数不预测真实表现
- 隐藏依赖、部分信息、"有益遗忘"场景

### SimpleMem（ICML 2026）
- 压缩 + 意图对齐检索：分层聚类 → 小模型摘要 → intent centroids → 意图感知检索
- F1 提升同时 token 大降，无需定制硬件；未解决时间推理

### EAM for GUI Agents（ICML 2026）
- GUI 动作+应用状态 = 知识图谱（节点=窗口/控件/输入，边=时序转移）；检索子图序列化
- 准确率提升+prompt token 大降；领域特定

### MRAgent（ICML 2026）
- "记忆是重构不是检索"：动态实体-事件-关系图，查询时遍历图重构情境视图
- LoCoMo/LongMemEval 提升最大在冲突信息+长依赖链场景；时间信号压制过时事实
- 代价：图维护计算开销

### MemEvolve（ICML 2026）
- 元学习进化记忆系统：同时优化"记什么"和"怎么记/取"（架构级）

## 四、基准与评测

### OSWorld 2.0（arXiv 2606.29537，2026-06/07）
- 108 个长程 computer-use 工作流；人类中位 1.6 小时/任务；Claude Opus 4.7 平均需 318 次工具调用（OSWorld 1.0 约 30）
- 挑战现象：流式交互、动态环境、跨源工作流
- 背景：computer-use agent 从 2024-04 OSWorld 12% → 2026-06 85%

### Gaia2（arXiv 2602.11964，Meta，2026-01/ICML 2026 周期）
- 异步动态环境：环境独立于 agent 演化、时间约束、噪声、歧义、多 agent 协作
- write-action verifier → 动作级评测 + 可直接用于 RLVR（verifiable rewards）

### DeepSWE（datacurve）
- 原创长程 SWE：prompt 约 SWE-bench Pro 一半长，但需 5.5x 代码量+2x 输出 token

### PerspectiveGap（2026-06/08）
- 多智能体编排 prompting 基准

## 五、自进化与自我开发

### Ouroboros（arXiv 2608.08311，2026-08）
- 自我开发 agent harness：工具/prompt/上下文组装/核心实现通过 reviewed commits 进化为后续运行时
- 双模式：递归自由进化（改进本身是任务）+ 经验驱动核心进化（日常暴露 bug）
- 战绩：Terminal-Bench 2.1 = 86.74%（Opus 5 run，最佳报告）；OSWorld-Verified = 90.69%（超此前最佳）；CL-Bench 0.2301 SOTA；161 天持续自我进化
- 安全议题：自我修改 agent 的边界

### EvolveR（ICML 2026）
- 经验驱动自蒸馏：从自身交互历史改进（对比只存 raw 或不改策略）

### Skill-Pro（arXiv 2602.01869，ICML 2026）
- 非参数 PPO 从经验学可复用技能，无参数更新（类似 Hermes skills 机制的学术版）

### SE-GA / CORAL / Agon
- SE-GA：GUI agent 记忆增强自进化；CORAL：共享持久记忆+异步执行的自进化多智能体（3-10x 改进率）；Agon：提示经济学全学科自动研究系统（18 角色 230KB prompt，30 天无人值守）

## 六、模型侧（Agent-native 基座）

### Kimi K3（2026-07-14 发布，2.8T 参数开源）
- 首个 3T 级开源模型；1M 上下文；原生视觉；thinking 常开（reasoning_effort low/high/max）
- Agent 基准：agentic tool use 类第 5（134 模型中，73.9/100）；OfficeQA Pro（PDF 全图像化）
- $2.60/M input，权重 7-27 开放

### GPT-5.6（Sol/Terra/Luna，2026-07）
- Sol 声称 Terminal-Bench 2.1 SOTA（第三方 88.8%）

### OX Alpha（8-22 披露）
- 27.8B dense 模型 Terminal-Bench 73.0 —— 一年前需数百 B 参数才能达到

### 竞赛格局（8 月）
- Terminal-Bench 2.1: GPT-5.6 Sol 88.8% > Ouroboros(Opus5) 86.74% > ...
- OSWorld: 85%（2026-06）但 OSWorld 2.0 长程版重置难度

## 七、工业里程碑（背景板）

- ICML 2026（首尔，7 月）：23,918 投稿创纪录；Google PAT 审 10000+ 稿（每篇 ~30 分钟）=史上最大 AI 同行评审部署
- Microsoft Build 2026（6-02）：ASSERT（政策驱动评测开源框架）+ ACS（Agent Control Specification，"agent 安全的 MCP"，5 检查点：input/LLM/state/tool/output）+ Rubric evaluator + Agent ROI
- Alphabet：token 处理量 2 年 300 倍（9.7T/月→3.2 quadrillion/月）；Gemini Spark 常驻个人 agent；Gemini 3.5 聚焦 agentic coding/长程
- NeurIPS 2026：7 月评审重发中

## 八、安全与治理（背景板）

- Prompt Injection as First-Class Vulnerability（2601.17548）：技能/工具/协议生态系统分析 → 需架构级缓解
- 多智能体安全开放挑战（2505.02077 v2 2026-04）：agentic web 身份互操作+生态级事件响应
- Agentic AI Security 综述（2510.23883 v2 2026-02）：输入治理/工具调用守卫
- Constitutional Black-Box Monitoring for Scheming（ICML 2026）

## 检索记录
- web_search（ddgs→tavily/parallel 后端）×12 查询
- arXiv 官方 abstract 直抓（代理 curl）：2608.06663 / 2606.29537 / 2608.08311 / 2602.16313 / 2608.19803 / 2602.11964
- mem0.ai ICML 2026 盘点全文（736KB HTML 解析）
- m0rtzz ICML2026 LLM Agent 42 篇清单
- masamasa59/ai-agent-papers、VoltAgent/awesome-ai-agent-papers（README）
