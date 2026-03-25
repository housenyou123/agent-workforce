# Nightly Retrospective — 每日回溯议程

## 目标
每晚对当天所有 Claude Code session 做结构化回溯，产出可执行的改进动作。
不自动改任何东西，只产出 insight + proposal，人类次日早上审批。

---

## 回溯内容（6 个模块）

### Module 1: 今日工作摘要
**数据源**: `~/agent-workforce/traces/{date}.jsonl`
**产出**: 结构化日报

回答这些问题:
- 今天做了多少个任务，涉及哪些项目
- 每个 agent 各承担了多少任务
- 总耗时、总成本(估算)
- 有多少任务有人类反馈，反馈分布如何

**输出格式**:
```json
{
  "date": "2026-03-26",
  "total_tasks": 12,
  "total_duration_min": 48,
  "total_cost_usd": 1.84,
  "by_project": {"pixelbeat-ios": 5, "dog-story-backend": 3, ...},
  "by_agent": {"ios_agent": 5, "backend_agent": 3, ...},
  "feedback_coverage": {"with_feedback": 4, "without": 8, "rate": 0.33}
}
```

---

### Module 2: 确定性验证审计
**数据源**: traces 中的 verification 字段
**目标**: 发现质量底线问题

检查项:
- 有多少任务跑了 build？通过率多少？
- 有多少任务跑了 lint？通过率多少？
- 有没有文件越界（修改了 workdir 外的文件）？
- 有没有凭据泄露风险？

**输出**: 违规列表（如果有）
```json
{
  "build_ran": 5, "build_passed": 4, "build_failed": 1,
  "lint_ran": 3, "lint_passed": 3,
  "boundary_violations": [],
  "credential_risks": [],
  "action": "trace tr_20260326_008 build 失败，需要检查"
}
```

---

### Module 3: 失败任务分析
**数据源**: auto_score < 0.5 或 human_feedback = thumbs_down 的 traces
**目标**: 找到失败的共性原因

对每个失败任务回答:
- 用户的目标是什么
- agent 做了什么（工具调用摘要）
- 失败信号是什么（被 revert？追问多次？手动重写？）
- 这个失败是 agent 能力问题，还是目标不清晰，还是外部依赖？

**输出**:
```json
{
  "failures": [
    {
      "trace_id": "tr_20260326_008",
      "goal": "...",
      "agent": "ios_agent",
      "failure_signal": "human_feedback=thumbs_down",
      "root_cause_category": "misunderstanding | poor_execution | scope_creep | broken_output | inefficient | external_blocker",
      "root_cause_detail": "一句话说明"
    }
  ],
  "patterns": "如果有 2+ 个失败属于同一类别，总结共性"
}
```

---

### Module 4: 成本分析
**数据源**: traces 中的 estimated_cost_usd 和 total_tokens
**目标**: 识别成本异常，找到优化空间

分析:
- 今日总成本 vs 过去 7 天日均
- 哪个 agent 最贵，是因为任务多还是单价高
- 有没有明显的"低价值高成本"任务（trivial 但花了很多 token）
- 成本趋势：上升/稳定/下降

**输出**:
```json
{
  "today_cost": 1.84,
  "7day_avg_cost": 1.52,
  "trend": "stable",
  "most_expensive_agent": "ios_agent",
  "most_expensive_task": {"trace_id": "...", "cost": 0.42, "goal": "..."},
  "optimization_suggestion": "如果有的话"
}
```

---

### Module 5: Profile 有效性评估
**数据源**: traces + profiles + 注入的 CLAUDE.md
**目标**: 判断当前 profile 是否在帮忙

检查:
- 今天有没有任务违反了 profile 里的 "cannot_do" 规则
- 今天有没有任务本该遵循 profile 的 "quality_gates" 但没做到
- 哪些 profile 的 lessons 被验证有用（同类任务不再失败）
- 哪些 profile 需要新增 lesson（同类任务重复失败）

**输出**:
```json
{
  "profile_violations": [],
  "quality_gate_misses": [
    {"agent": "ios_agent", "gate": "支持 Dark Mode", "trace": "tr_20260326_005"}
  ],
  "lessons_validated": [],
  "lessons_needed": [
    {"agent": "backend_agent", "suggestion": "MongoDB aggregation 任务需要先确认 index"}
  ]
}
```

---

### Module 6: 改进提案
**数据源**: Module 2-5 的输出
**目标**: 生成具体的、可审批的改进动作

提案类型:
1. **profile_lesson**: 给某个 agent 的 profile 增加一条 lesson
2. **quality_gate**: 给某个 agent 增加一个质量检查项
3. **routing_fix**: 某类任务应该路由给不同的 agent
4. **cost_optimization**: 某类任务可以用更便宜的模型
5. **workflow_step**: 给某个 agent 的工作流增加一步

每个提案必须包含:
- 改什么
- 为什么改（引用哪些 trace 作为证据）
- 预期效果
- 风险（改了可能引入什么问题）

**输出**:
```json
{
  "proposals": [
    {
      "type": "profile_lesson",
      "target_agent": "ios_agent",
      "content": "SwiftData 迁移必须先检查旧 CoreData stack",
      "evidence": ["tr_20260326_005", "tr_20260325_012"],
      "expected_effect": "SwiftData 相关任务成功率从 60% 提升到 85%",
      "risk": "可能增加 SwiftData 任务的执行时间"
    }
  ]
}
```

---

## 回溯频率和输出

| 时间 | 做什么 | 输出到哪 |
|------|--------|---------|
| 每晚 | 6 个模块全跑 | `reports/{date}.json` + 飞书 #每日报告 |
| 每周日 | 7 天汇总趋势 | `reports/weekly_{date}.json` + 飞书 |
| 每月 1 号 | Agent 健康评估 | `reports/monthly_{date}.json` + 飞书 |

## 回溯的执行前提

必须有足够数据才有意义:
- **Module 1-2**: 任何时候都可以跑（只要有 trace）
- **Module 3**: 需要有 feedback 数据（至少 3 个 thumbs_down）
- **Module 4**: 需要 7+ 天的 traces 才能看趋势
- **Module 5**: 需要 profile 已注入到 CLAUDE.md 且被使用
- **Module 6**: 需要 Module 3-5 有输出

## 回溯不做的事

- 不自动修改 profile YAML
- 不自动修改 CLAUDE.md
- 不自动修改 enforcement.yaml
- 不自动部署任何东西
- 不自动创建新 Agent

所有改动都是 proposal，推飞书等人类确认。
