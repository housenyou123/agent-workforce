# ADR-003: 完成度和质量分开评分

## 状态
已采纳 (2026-03-25)

## 背景
初版用单一 auto_score 混合打分，无法区分"做完了但质量差"和"没做完"。Codex GOAL_COMPLETION_SPEC 提出双维度。

## 决策
分为 Completion Score (是否完成) 和 Quality Score (完成质量)。

## 理由
1. "做完了但 build 没过"和"根本没做"是不同类型的问题
2. 确定性验证 (build/lint/scope) 决定 completion，不应该被 human_feedback 覆盖
3. 分开统计才能精准定位：agent 的问题是"不会做"还是"做不好"

## Completion Score 权重
- deliverables_met: 35%
- verification_passed: 35%
- scope_respected: 15%
- contract_respected: 10%
- handoff_ready: 5%
- verification 没过 → 最高 0.59
- scope 越界 → 直接 0

## Quality Score 权重
- deterministic_checks: 40%
- review_result: 20%
- human_feedback: 20%
- implicit_signals: 20%
