# ADR-001: Claude-Native 而非独立 Runtime

## 状态
已采纳 (2026-03-25)

## 背景
调研了 10+ 框架 (rd-agent, LangGraph, CrewAI, AutoGen, EvoAgentX 等) 后，需要决定系统的运行时架构。

## 决策
在 Claude Code 原生能力上扩建，不引入独立的 multi-agent runtime。

## 理由
1. 用户是独立开发者，维护不了额外框架
2. 已有 34 个 Claude Code skills + hooks + session-handoff 生态
3. rd-agent 绑定 Docker + 数据科学场景，改造成本 > 新建
4. LangGraph/CrewAI 需要维护独立 Python 服务
5. Claude Agent SDK 最接近但仍是额外依赖

## 后果
- Agent Workforce 是 Claude Code 的增强层，不是替代品
- Profile 通过 CLAUDE.md 注入，不是独立 agent 进程
- 系统边界清晰：hooks + trace + server + nightly eval
