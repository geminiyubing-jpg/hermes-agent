# TASK-001 核实记录

## 已验证（有数据文件背书）
1. 今日审计数字：expGPT2_audit.json = base 2.658 / R0_task 0.614 / anti 0.474 /
   random null p50 0.452 / span angle 7.5°——与 LAB_NOTEBOOK L1370-1371 一致
2. 历史数字：expP3_rotation_results.json = R(0°) med 0.928（即「历史 0.91-0.96」的来源之一；
   LAB_NOTEBOOK L672/L699 另有 M2 口径 0.911/0.928 记录）
3. 两脚本口径四因子差异：逐行 diff 确认（见 DELIVER.md 表）
4. 状态机脱节事实：TASK_RUNTIME.md（11:47 写入）vs LAB_NOTEBOOK 13:35 收口条目

## 未验证（本次工具受限）
- expFactorScan_output.txt（13:32，764B）：13:35 收口条目数字（0.905-0.960、
  中心化-0.25、末位-0.03）的疑似数据源，未能读取
- scratch 里两份消融脚本（audit_v2 阶梯版 / gap_ablation 2^4 网格版）均无对应输出 json
  → 13:32 的 FactorScan 是第三份脚本，其 .py 不在 scratch 也不在 /tmp 主列表（可能内联在对话里）

## 环境教训（记录给后续唤醒）
- scratch 目录的默认 python 无 transformers，实验须在主环境跑
- terminal/filesystem MCP 均有熔断机制：失败后勿连续重试，冷却计数会刷新
- filesystem MCP 硬性限制：只允许 /Volumes/DATA 和 /Users，/tmp 读写均被拒
- tool_call 数组元素格式：顶层键只能是 name+arguments，多余键会直接报错
