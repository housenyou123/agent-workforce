# Agent Workforce

AI Agent 协作平台 — 白天生产，晚上进化。

## 架构概述

```
Human (飞书群交互)
    │
    ▼
Orchestrator (Opus) ── 任务拆分 + 路由 + 仲裁
    │
    ├── iOS Agent (Sonnet)      ── Swift/SwiftUI 原生开发
    ├── Backend Agent (Sonnet)  ── Node.js/Python 服务端
    ├── Web Agent (Sonnet)      ── React/Next.js 前端
    ├── Data Agent (Sonnet)     ── 数据分析/ML/VLM
    └── Infra Agent (Haiku)     ── 脚本/CI/配置 (不直接操作远程)
          │
          ▼
      Reviewer (Sonnet) ── 交叉审查 + 质量门禁
          │
          ▼
      Trace Store ── 全量日志 (JSONL)
          │
          ▼ (每晚)
      Nightly Evaluator ── Qwen3.5-35B 本地评测
          │
          ▼
      Profile Evolution ── 自动/人工审批升级
```

## 核心原则

1. **执行层隔离，数据层聚合** — 每个项目在独立 sandbox 中执行，trace 统一汇聚
2. **Claude Only** — 不引入外部 API，全部用 Claude 模型 + 本地 Qwen
3. **人类确认三件事** — 新增 Agent / 模式切换 / 规则修改
4. **飞书群反馈** — 所有审批、反馈、日报通过飞书群交互

## 规则体系

- **P0 (绝对禁止)** — Hook 硬拦截: 文件边界、凭据隔离、生产保护、不可逆操作
- **P1 (必须遵守)** — Review 检查: 上游只读、禁止直接通信、单一职责、输出可验证
- **P2 (强烈建议)** — Trace 记录: 先读后改、最小变更、成本意识
- **P3 (最佳实践)** — 夜间统计: 不确定时先澄清、拆步骤、自检

## 目录结构

```
agent-workforce/
├── profiles/           # Agent Profile (版本化 YAML)
│   ├── orchestrator/
│   ├── ios_agent/
│   ├── backend_agent/
│   ├── web_agent/
│   ├── data_agent/
│   ├── infra_agent/
│   └── reviewer/
├── rules/              # 行为规则 (enforcement.yaml)
├── traces/             # 任务轨迹 (JSONL, 按日分片)
├── artifacts/          # 产物注册表
├── knowledge/          # 进化知识库
│   ├── failure_patterns/
│   ├── routing_rules/
│   └── benchmark/
├── evolution/          # 夜间评测引擎
├── reports/            # 每日评测报告
├── hooks/              # Claude Code Hooks
├── scripts/            # 工具脚本
└── docs/               # 项目文档
```

## 飞书群话题

| 话题 | 用途 |
|------|------|
| #任务进展 | Agent 完成任务后自动通知 |
| #审批请求 | reject / 新 Agent / 规则变更 / 部署确认 |
| #每日报告 | 夜间评测报告 |
| #紧急告警 | P0 违反 / Agent 异常 |
| #进化记录 | Profile 升级、知识沉淀的变更日志 |

## 快速开始

```bash
# 查看 Agent 状态
python cli.py status

# 手动触发夜间评测
python cli.py evaluate --date 2026-03-25

# 查看某个 Agent 的历史表现
python cli.py report --agent ios_agent --days 7
```
