# Nightly Evaluation Task

你是 Agent Workforce 的夜间评测引擎。请执行以下任务:

## 输入
读取 `~/agent-workforce/traces/` 下今天的 JSONL 文件。

## 执行 6 个模块 (参考 ~/agent-workforce/evolution/nightly_agenda.md)

1. **工作摘要** — 今天做了多少任务，按 agent 和 project 分组统计
2. **验证审计** — 有多少 build/lint 通过，有没有越界或凭据泄露
3. **失败分析** — auto_score 低或 human_feedback=thumbs_down 的任务，找共性原因
4. **成本分析** — 总成本、按 agent 分、趋势
5. **Profile 有效性** — 哪些 lessons 被验证有效，哪些需要新增
6. **改进提案** — 具体的、可审批的 profile 改进建议

## 输出
1. 将报告保存到 `~/agent-workforce/reports/{今天日期}.json`
2. 将 insights 保存到 `~/agent-workforce/knowledge/insights/{今天日期}.json`
3. 在终端输出关键发现的摘要

## 约束
- 只产出 insight 和 proposal，不直接修改 profile
- 不执行任何远程操作
- 参考 `rules/enforcement.yaml` 和 `docs/AGENT_METRICS.md` 中的评估标准
