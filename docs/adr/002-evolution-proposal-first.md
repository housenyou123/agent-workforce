# ADR-002: 进化采用 Proposal-First，不自动改 Profile

## 状态
已采纳 (2026-03-25)

## 背景
初版设计中 nightly evaluator 会自动升级 profile (promote_profile.py)。Codex review 指出这过于激进。

## 决策
夜间评测只产出三层输出：insight → proposal → regression result。不直接修改 profile。

## 理由
1. 学习信号还不够干净（goal 靠 hook 捕获，build 结果未确认 exit_code）
2. 自动改 profile 的风险：一个错误的改动会影响所有后续任务
3. Constitution 原则："宁可明确失败，也不要模糊成功"
4. Google DeepMind 研究：agent 系统复杂度需要严格控制

## 后果
- promote_profile.py 归档到 _archive/
- 所有改进提案推飞书等人类确认
- Golden example 积累到 20+ 且 exit_code 采集完善后，可以考虑半自动升级
