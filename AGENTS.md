# AGENTS.md

## 先读什么

进入本仓库后，默认按以下顺序获取上下文：

1. [constitution.md](/Users/housen/agent-workforce/constitution.md)
2. [CONTEXT.md](/Users/housen/agent-workforce/CONTEXT.md)
3. [rules/enforcement.yaml](/Users/housen/agent-workforce/rules/enforcement.yaml)
4. 对应 agent profile
5. 当前任务相关 docs / scripts / server / hooks

如果任务涉及架构、协作、完成定义、演进策略，再补读：

- [docs/ARCHITECTURE_RECOMMENDATION.md](/Users/housen/agent-workforce/docs/ARCHITECTURE_RECOMMENDATION.md)
- [docs/GOAL_COMPLETION_SPEC.md](/Users/housen/agent-workforce/docs/GOAL_COMPLETION_SPEC.md)
- [docs/AUTORESEARCH_ADAPTATION.md](/Users/housen/agent-workforce/docs/AUTORESEARCH_ADAPTATION.md)

---

## 项目概览

Agent Workforce 是一个围绕 Claude Code 构建的 AI 协作平台。

核心目标：

- 白天让 AI agents 在受控边界内执行任务
- 夜晚基于 trace、反馈和规则做评测与演进

当前重点不是做一个重型 agent swarm，而是把这条闭环做稳：

- hooks
- trace
- server
- feedback
- review / verification
- nightly evaluation

---

## 当前工作方式

本项目默认采用 Claude-native 协作方式：

- 以 session / run 为最小执行单元
- 以规则文件和结构化文档作为主要上下文
- 以 trace 和 artifact 作为可审计记录
- 以人类审批作为高风险动作的安全阀

不要把这个仓库当成“自由探索型 agent playground”。

它更接近：

- 协作操作系统
- 任务编排系统
- 反馈与演进系统

---

## 工作规则

### 1. 参考资料优先

如果任务可以被已有参考资料回答，先引用参考资料，不直接脑补。

优先参考：

- `constitution.md`
- `CONTEXT.md`
- `rules/enforcement.yaml`
- `profiles/*.yaml`
- `docs/*.md`

输出时尽量区分：

- `事实`
- `推断`
- `建议`

不要把推断写成既成事实。

### 2. 先规则，后实现

如果当前任务涉及以下内容，优先补规则或 spec，而不是直接改代码：

- 新协作流程
- 新 agent 运行方式
- 新完成定义
- 新 review 规则
- 新 evolution 策略

对于非 trivial 任务，开始前默认要有最小 Done Spec：

- `goal`
- `deliverables`
- `verification`
- `constraints`
- `completion_status`

### 3. Fast fail

出现以下情况时，暂停继续生成产出，先暴露缺口：

- 上下文冲突
- 验收缺失
- contract 缺失
- 错误无法诊断
- 需要人类审批但尚未审批

连续两次关键验证失败时，不要继续堆补丁；先总结失败信号和可能根因。

### 4. Don’t fallback

不要为了“先跑起来”而：

- 猜 contract
- 自动补默认业务逻辑
- 静默吞错误
- 用模糊结论替代明确失败

错误信号必须尽量保真：

- 保留真实报错
- 保留调用栈
- 保留关键日志
- 保留触发条件

不要把现场抹平到无法诊断。

### 5. Single source of truth

以下对象必须围绕唯一可信来源工作：

- 项目规则：`rules/enforcement.yaml`
- 项目背景：`CONTEXT.md`
- agent 身份与边界：`profiles/*.yaml`
- 完成定义：`docs/GOAL_COMPLETION_SPEC.md`
- 架构方向：`docs/ARCHITECTURE_RECOMMENDATION.md`

如果某个关键信息无法回指到权威文件，优先把它补进权威文件，而不是继续停留在对话里。

### 6. Evidence-first 输出

任务完成或阶段性汇报时，默认至少回答四件事：

1. 改了什么
2. 依据什么改
3. 怎么验证的
4. 还有什么风险

只给结论不给证据，不算高质量交付。

---

## 关键路径

### 主要目录

- `profiles/`
  agent profile 定义
- `rules/`
  行为约束
- `hooks/`
  Claude Code hooks
- `scripts/`
  trace / envelope / notify 等核心逻辑
- `server/`
  FastAPI 服务端与 Dashboard
- `evolution/`
  夜间评测与演进逻辑
- `docs/`
  架构和规范文档

### Agent 编队 (v2.0, 2026-04-02 进化)

| Agent | Model | 覆盖 | Trace占比 |
|-------|-------|------|----------|
| Backend Agent | Sonnet | 6 个后端项目 (TS+Python+Go) | 28% |
| **NetOps Agent** 🆕 | Sonnet | VPN/网络诊断/云网络/代理服务 | ~28% (原归 Backend) |
| Infra Agent | Sonnet | 脚本/CI/配置/AW系统本身 | 16% |
| Web Agent | Sonnet | 5 个 Web 前端项目 | 10% |
| Data Agent | Sonnet | UGC/VLM/数据分析 | 9% |
| iOS Agent | Sonnet | PixelBeat/DogStory/IPGuard | 5% |
| Orchestrator | Opus | 路由参考 (非独立运行) | — |
| Reviewer | Sonnet | 验证清单 (非独立运行) | — |

### 三级路由 (v2.0)

1. **路径匹配**: cwd → `config.yaml:project_routes` 精确匹配
2. **Session 继承**: 短指令/auto session → 沿用上一条 trace 的 project
3. **内容推断**: goal 关键词 → `trace_schema._CONTENT_KEYWORDS` 匹配

### 核心链路

1. 用户提出目标
2. Claude Code hooks 捕获 goal / tool usage / stop
3. trace 落本地 JSONL (含三级路由 + auto_rate v2 + 边界检测)
4. 服务端双写到 SQLite
5. 飞书接收反馈 / 审批
6. nightly evaluator 汇总并产出 insight / proposal

---

## 当前约束

### 不要做的事

- 不把聊天记录当权威规则源
- 不在缺 contract 时强行做跨端协作
- 不把 fallback 当正常策略
- 不把“看起来像完成”当真正完成
- 不在高风险动作上绕过人类确认
- 不静默扩大 scope
- 不在缺 Done Spec 的情况下长距离实现

### 默认要做的事

- 先识别参考资料
- 先识别唯一可信来源
- 先明确完成定义和验证方式
- 再进入实现或改造
- 结束时回传证据，不只回传结论

如果任务较大，优先把关键决策沉淀进 docs，而不是只留在对话里。

---

## 常用命令

```bash
python3 /Users/housen/agent-workforce/cli.py status
python3 /Users/housen/agent-workforce/cli.py traces --date 2026-03-25
python3 /Users/housen/agent-workforce/cli.py report --days 7
python3 /Users/housen/agent-workforce/cli.py evaluate --date 2026-03-25
```

---

## Evolution V2 (2026-04-02)

基于 537 条 trace 的回顾分析，执行了以下进化：

| 提案 | 效果 |
|------|------|
| P0 auto_feedback 回补 | 覆盖率 51% → 100% |
| P1 三级路由 | unknown 率 44% → 25% |
| P2 NetOps Agent | VPN 项目独立路由 |
| P3 边界检测 | 检出 36 条越界 (6%) |
| P5 auto_rate v2 | good 93% → 40%, golden 0% → 52% |
| P6 interview-bot 路由 | 新增 68 条项目归属 |

### 下一步

1. **观察新 trace 的 unknown 率** — 三级路由在实时场景下预期 <15%
2. **auto_rate v2 校准** — 观察 golden 52% 是否过高，可能需要收紧
3. **夜间评测** — 数据充足后跑 `evolution/nightly_eval.py --engine claude`
4. **NetOps profile 注入** — 在 VPN 项目的 CLAUDE.md 中引用 profile
