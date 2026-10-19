# Agent 演进史培训：从规则系统到自主智能体

> 源材料：2026-08 最新研究综述（arXiv API + HuggingFace Daily Papers 一手数据，本会话两轮检索 ~80 篇）
> 用途：内部培训 PPT 源文档

## 一、前史：Agent 概念的三个源头（1950s-2010s）

1. **符号主义 Agent**（1956-1990s）：GPS 通用问题求解器、专家系统 MYCIN。规则+推理引擎， brittle but explainable。
2. **反应式 Agent**（1986-）：Brooks 行为主义 Subsumption Architecture，"智能不需要表征"。
3. **RL Agent**（1998-2010s）：SARSA、Q-learning、DQN（2015）。马尔可夫决策过程，奖励驱动。

## 二、LLM Agent 纪元（2022-2024）

### 2.1 奠基三件套
- **ReAct**（2022.10，Yao et al.）：推理+行动交织，Thought→Action→Observation 循环。一切现代 agent 的骨架。
- **Toolformer**（2023.2，Meta）：模型自己学会何时调 API。
- **AutoGPT**（2023.3）与自主循环狂热：目标驱动长任务，暴露记忆/规划短板。

### 2.2 记忆与规划分层
- **Voyager**（2023.5）：技能库 + 自动课程，Minecraft 里终身学习。
- **Generative Agents**（2023.4，斯坦福）：记忆流 + 反思机制，25 个小镇居民涌现社会行为。
- **Tree of Thoughts**（2023.5）：搜索式推理，规划从链到树。
- **Reflexion**（2023.3）：语言反馈强化，失败后口头反思重试。

## 三、多智能体与工作流工程（2024-2025）

- **MetaGPT / Camel / AutoGen**：多角色协作框架，SOP 软件公司隐喻。
- **Computer-Use / GUI Agent**：Claude computer use（2024.10）、UI-TARS、OS Agents 落地。
- **DeepResearch 类**：搜索+综合长任务，OpenAI Deep Research（2025.2）。
- **Agent Skills / MCP**（2024.11-2025）：Anthropic MCP 协议标准化工具接入；Claude Skills（2025.10）知识包。
- **Agent Harness 概念成型**：工具+上下文+控制流的管理层成为能力天花板。

## 四、2026 当前前沿：四大主线（8月最新）

### 4.1 Harness-Native Agentic RL（8/17-18 五篇撞车）
- **Agent Lightning v1.0**：解耦架构，任意 harness ↔ RL 训练器。
- **LEGO-RL**：coding agent 的 harness 原生 RL。
- **ClawGym II**：黑盒 RL 直接跑在 harness 上。
- **Agentic ESOpt**：进化策略微调，消费级 GPU 可跑。
- **Cooperative Coevolution**：资源受限协同进化。
- **范式信号**：RL 训练对象从"模型"变成"整个 agent 系统"。

### 4.2 Test-Time Compute 精细化
- **CLR**（Claim-Level Reliability）：算力从多采样重分配到定向验证。
- **DCR**（发散-收敛推理）：两阶段原语。
- **RLVR 难度调度**：图结构在线难度估计分配 rollout 预算。
- **趋势**：verification 正在吃掉 sampling 的预算。

### 4.3 Agent 记忆系统成熟
- **MELD**：跨 agent 记忆合并协议（分布式 CAP 问题重演）。
- **MemoryLake/MemoryArena**：记忆底座系统性评测。
- **原始聊天记录检索 ≈ 结构化记忆**（反直觉发现）。
- **LycheeMemory V2**：语义分段级合并降成本。

### 4.4 可靠性经济学时代
- **Fragility of Self-Improving Agents**：方差/任务顺序/欠约束三重脆弱性。
- **HarnessRisk**：harness 全生命周期安全基准。
- **Agentic Transaction**：给 agent 上 ACID 事务语义。
- **Behavioral Contracts II**：组合可靠性独立性假设被证伪。
- **ASCon**：多 agent 故障归因。
- **趋势判断**：从"能力展示"转向"可靠性经济学"——错误预算+签字担保。

## 五、能力分层模型（培训核心图）

L0 聊天助手（指令跟随）
L1 工具调用者（function calling, ReAct）
L2 工作流执行者（SOP、多步骤、CI 式）
L3 自主规划者（目标驱动、动态分解、自纠错）
L4 自进化系统（记忆沉淀、技能习得、经验复用）
L5 多智能体生态（协作、协议、治理）

判别问题：遇到 X 情况它自己会怎么办？

## 六、关键启示（培训落点）

1. Agent 能力天花板在 **harness 设计**，不在模型本身。
2. **记忆是基础设施**：跨会话任务完成 > 事后召回。
跨 agent 合并协议是下一站。
3. **验证比生成值钱**：test-time 算力向 verification 迁移。
4. **可靠性 = 新竞争力**：错误预算、行为合同、审计框架。
5. 生产落地三问：错误预算多少？谁签字担保？审计接口在哪？
