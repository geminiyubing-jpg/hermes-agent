# 主对话转发用简报

TASK-001（GPT-2 复现缺口）核实结果：任务实际已于 13:35 收口（主对话+任务代理协作），
但 TASK_RUNTIME.md 状态机未同步（仍 active/0%）。

核实证据链：
- 今日数字 0.614（expGPT2_audit.json）✓
- 历史 0.928（expP3_rotation_results.json）✓
- 根因=四因子口径差异（中心化 -0.25 主导 + 末位提取 -0.03 + k + prompts）
- 13:35 收口条目引用的消融输出 expFactorScan_output.txt 本次未能读取（工具熔断），
  待下次唤醒验证数字（预计 1 分钟）
- 后续 20:27 诊断D 已把 R0 降级为筛查统计量，不影响「历史数据可复现」结论本身

行动：下次唤醒先读 expFactorScan_output.txt → 状态机改 done → 本简报可删。
