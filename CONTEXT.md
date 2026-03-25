# Agent Workforce — 项目完整上下文

## 一句话描述
AI Agent 协作平台：白天多 Agent 自动执行任务 + 交叉 Review，晚上自动评测进化。

## 项目目标
让一个独立开发者 (housen) 的 24 个项目的 AI 协作效率极大提升。未来大部分工作由 sub-agent 完成，agent 之间交叉 review，系统每晚自动学习进化。

## 当前状态
**Phase 0 完成 + 服务端上线** — 基础设施搭建完毕，自动监控已生效，飞书反馈闭环已通。

---

## 任务背景：这个项目是怎么来的

### 起因
用户 (housen) 是一个独立创业者，同时维护 24 个代码项目（PixelBeat、Dog Story、Spot Playground 等），涵盖 iOS、后端、Web、数据分析、基础设施五条线。他日常高度依赖 Claude Code 做开发，但存在几个核心痛点：

1. **经验不复用** — 每次 Claude Code 对话重新开始，之前踩过的坑不会自动避免
2. **无法对比** — 同类任务用不同策略做过，但没有结构化记录来比较
3. **进化靠直觉** — 反馈没有系统化沉淀，agent 不会自动变好
4. **路由靠人脑** — 什么任务该怎么拆、用什么工具、什么约束，全凭每次口述

### 用户给的初始输入
1. 一段 ChatGPT 对话 — 描述了"白天生产、晚上进化"的双循环系统构想
2. Microsoft rd-agent 的 GitHub 链接 — 作为参考框架
3. 要求结合本地项目现状调研更好的方案

---

## 完整构建过程：做了什么 + 用户反馈 + 如何回应

### Phase 1: 调研 (用户要求先调研后决策)

**做了什么**：
- 深入研究 rd-agent 源码架构 (CoSTEER、EvolvingStrategy、KnowledgeBase)
- 调研 10+ 替代框架 (LangGraph、CrewAI、AutoGen、Claude Agent SDK、DSPy、EvoAgentX、TextGrad、ADAS)
- 读取用户本地 24 个项目的完整信息 (memory 文件、CLAUDE.md、skills、plans)
- 分析用户已有的多 agent 模式 (Dog Story 5-agent、PixelBeat 7-agent)

**产出**：框架对比表 + 推荐方案

**关键决策**：不引入新框架，在 Claude Code 生态上扩建。原因：
- rd-agent 绑定 Docker + 数据科学场景，改造成本 > 新建
- LangGraph/CrewAI 需要维护独立 Python 服务，一个人扛不住
- 用户已有 34 个 skills + ralph-loop + session-handoff + Telegram AFK，生态很成熟

### Phase 2: 架构设计

**做了什么**：
- 设计 7 个 Agent 编队 (Orchestrator + 5 Worker + Reviewer)
- 设计 Task Envelope + Artifact Registry 的信息串联协议
- 设计交叉 Review 矩阵 (每个 Agent 既是生产者也是其他 Agent 的 Reviewer)
- 设计 Trace 数据结构 (自动采集层 + 衍生计算层)
- 设计三级反馈体系 (无感采集 / 快捷标记 / 结构化评价)
- 设计夜间进化引擎 (本地 Qwen3.5-35B，零云成本)

**用户反馈 1**："不同的项目在执行层要隔离，但是在数据层要聚集"
- **回应**：设计了 Execution Sandbox (每个项目独立 workdir) + 统一 Trace Store (所有项目的 trace 汇聚)

**用户反馈 2**："这些规则要非常强的执行"
- **回应**：设计了 P0-P3 四级规则体系，P0 由 Hook 硬拦截不可绕过

**用户反馈 3**：明确三个必须人类确认的事项
- 新增 Agent
- 工作模式切换 (生产 ↔ 评测)
- 规则修改 (二次确认)
- **回应**：写入 enforcement.yaml 的 human_approval_required 部分

**用户反馈 4**："我们用一个飞书群来进行对人类的反馈交互"
- **回应**：设计飞书群 5 个话题 (#任务进展 / #审批请求 / #每日报告 / #紧急告警 / #进化记录)

**用户反馈 5**："所有部署相关的事情都需要人类确认"
- **回应**：加入 P1-006 规则，Infra Agent 只写脚本不执行

### Phase 3: 编码实现

**做了什么**：
- 创建项目目录结构
- 编写 enforcement.yaml (4条P0 + 6条P1 + 5条P2 + 3条P3)
- 编写 7 个 Agent Profile YAML (orchestrator/ios/backend/web/data/infra/reviewer)
- 编写 trace_schema.py (Trace 数据结构 + auto_score 计算 + 场景匹配)
- 编写 envelope.py (Task Envelope + Artifact Registry)
- 编写 feishu_notify.py (5 种消息模板)
- 编写 nightly_eval.py (夜间评测引擎)
- 编写 cli.py (status/profiles/traces/evaluate/report/feedback)
- 编写 claude_code_hook.sh (Shell 快捷命令 aw1-4, aws, awt)
- 编写 USER_GUIDE.md

**用户反馈 6**："我应该如何用起来呢，可能的用户故事是怎么样"
- **回应**：写了 6 个完整用户故事（早上看报告、开始任务、任务完成、跨端协作、问题拦截、晚上自动进化），同时做了 UX 分析发现系统是"写好了但没接上"，补写了 claude_code_hook.sh 集成层

**用户反馈 7**："aw3 这些是什么来着"
- **回应**：推了一张飞书速查卡片到群里，方便随时查看

**用户反馈 8**："现在所有 claude 的任务都被监控起来了吗"
- **回应**：发现还是手动模式，于是写了 4 个 Claude Code Hook:
  - SessionStart → 清空临时文件
  - UserPromptSubmit → 捕获用户目标
  - PostToolUse (Bash|Edit|Write) → 异步记录工具调用
  - Stop → 汇总 trace + 推飞书

**用户反馈 9**："我调教你这个平台的数据也需要记录下来，你可以自己迭代你自己"
- **回应**：把整个设计过程沉淀到 knowledge/ 目录 (bootstrap_lessons.md、routing_rules、golden_examples)

**用户反馈 10**："对每个 session 的反馈，能不能自动在任务结束后推到飞书"
- **回应**：修改 Stop hook，session 结束后自动推飞书通知

**用户反馈 11**："是不是不应该每个 query 都问我" + "什么信息需要加在推送里"
- **回应**：
  1. 加了推送过滤规则：只推重要任务 (>5min / >10 calls / build失败 / 追问>5次)
  2. 精简推送内容：只保留 项目名 + agent + 耗时 + goal + 按钮

**用户反馈 12**："这里的按钮没了"
- **回应**：把按钮加回来，和文字提示并存

**用户反馈 13**："所有监控日志和反馈数据可以存储在服务端" + "避免数据丢失"
- **回应**：
  1. 写了 FastAPI 服务端 (server/app.py)：SQLite 存储 + Dashboard + Feedback API
  2. 修改 Stop hook 为双写模式：本地 JSONL + 远程 SQLite
  3. 部署到火山云 ECS (118.196.147.14:9100)

**用户反馈 14**："如果我点了这些按钮，你会有什么对应的动作呢"
- **回应**：发现飞书 webhook 机器人按钮没有回调能力，改为 URL 跳转型按钮，点击直接打开浏览器完成反馈

**用户反馈 15**："记下来每个任务在提出后、执行前都想一想用户场景和测试 case"
- **回应**：记录为 feedback_dev_process.md，后续所有任务先列场景 + case + 回归测试

**用户反馈 16**："要把任务 context、你做了什么、用户反馈、你怎么回应的都加进来"
- **回应**：就是这份文档

---

## 架构详情

### Agent 编队 (v1.0)

| Agent | Model | 覆盖项目 | 关键约束 |
|-------|-------|---------|---------|
| Orchestrator | Opus | 全局调度 | 不写业务代码，不跳过 review |
| iOS Agent | Sonnet | PixelBeat/DogStory/IPGuard | 不引入第三方 SDK，不定义 API |
| Backend Agent | Sonnet | 6 个后端 (TS+Python) | 拥有 shared/ 目录，不改 prompt 文案 |
| Web Agent | Sonnet | 5 个 Web 前端 | 不做后端/iOS/数据库 |
| Data Agent | Sonnet | UGC/VLM/数据分析 | 严格只读原始数据 |
| Infra Agent | Haiku | 脚本/CI/配置 | 只写脚本不执行，所有远程操作需人类确认 |
| Reviewer | Sonnet | 交叉审查 | 不能自审，不能直接改被审代码 |

### 交叉 Review 矩阵

```
产出 Agent    →  Review Agent    →  审查维度
iOS Agent     →  Backend Agent   →  API 调用一致性、错误处理
Backend Agent →  iOS Agent       →  返回数据是否满足 UI 需求
Web Agent     →  Backend Agent   →  API 对接、数据格式
Data Agent    →  Web Agent       →  可视化可行性、数据格式
Infra Agent   →  Backend Agent   →  配置正确性、安全
```

### Verdict 处理

- **pass** → 直接合并
- **concern** → 产出 Agent 自动修复，最多 2 次，超过升级为 reject
- **reject** → 暂停，推飞书群等人类决策

### 信息串联协议

- **Task Envelope** — 所有 Agent 共享的任务上下文 (goal + constraints + subtasks + contracts)
- **Artifact Registry** — Agent 产物注册表 (final / discovery / review 三种类型)
- **核心原则**：信封不变产物追加、传摘要不传全文、Contract 先行实现后行

### 规则体系 (enforcement.yaml)

- **P0 (4条, Hook 硬拦截)**: 文件系统边界、凭据隔离、生产环境保护、不可逆操作
- **P1 (6条, Review 检查)**: 上游只读、禁直接通信、单一职责、可验证、契约广播、部署确认
- **P2 (5条, Trace 扣分)**: 先读后改、最小变更、错误处理边界、成本意识、格式一致
- **P3 (3条, 统计优化)**: 不确定先澄清、拆步骤、自检
- **HA (4条, 人类确认)**: 新增Agent、模式切换、规则修改、部署

### Trace 系统

**自动采集 (零摩擦)**：
- trace_id, timestamp, project, scenario, agent_profile
- goal (从 UserPromptSubmit hook 捕获)
- tool_calls, files_modified, duration_sec, rounds

**隐式信号 (夜间计算)**：
- output_committed (git commit 检测)
- human_post_edit_ratio (你改了多少)
- follow_up_count (追问次数)
- frustration_detected (NLP 检测 "不是这样")
- reverted (git revert 检测)

**auto_score 计算规则**：
- reverted → 0.1 (确定失败)
- post_edit_ratio > 0.5 → 0.2 (基本重写)
- committed + post_edit < 0.05 → +0.4 (直接用了)
- build_success=false → -0.3
- follow_up > 3 → -0.2
- 👍 覆盖 → 0.85+, 👎 覆盖 → 0.3-

### 飞书推送规则

**推送条件** (只推重要的，不刷屏)：
- 耗时 > 5 分钟
- 工具调用 > 10 次
- build 失败
- 追问 > 5 次

**推送内容**：
- 项目名 · Agent · 耗时
- 用户的原始目标
- 👍🔄👎⭐ 四个按钮 (URL 跳转到服务端 feedback API)

### 夜间评测引擎

运行在本地 Qwen3.5-35B (:8801)，每晚 2:00 触发：
1. 加载当天所有 traces
2. 按 agent 分组，计算成功率/成本/耗时
3. 识别失败模式 (用 LLM 分析共性)
4. 生成 profile 改进提案
5. 用 golden examples 回归测试
6. 通过 (>5% 提升) → 自动升级；否则 → 推飞书等确认

### Agent 自我进化的 4 个层次

| 层次 | 触发 | 审批 |
|------|------|------|
| Layer 1: 知识积累 (golden examples + failure patterns) | 每次任务自动 | 无需 |
| Layer 2: Prompt 进化 (system prompt 措辞优化) | 夜间评测 | auto_score 提升 >5% 自动升级，否则飞书确认 |
| Layer 3: 工作流进化 (执行步骤调整) | 同类失败 3+ 次 | 必须飞书确认 |
| Layer 4: 架构进化 (拆分/合并 Agent) | 月度 review | 必须飞书确认 |

---

## 服务端

- **位置**: 火山云 ECS 118.196.147.14:9100
- **进程**: uvicorn, AW_DB_PATH=/data/agent-workforce/traces.db
- **API**:
  - `POST /api/traces` — 接收 trace
  - `GET /api/feedback?trace_id=xxx&rating=3` — 接收反馈 (飞书按钮跳转)
  - `GET /api/traces?date=&agent=&project=` — 查询
  - `GET /api/stats?days=7` — Agent 统计
  - `GET /` — Web Dashboard
- **状态**: ✅ 已部署并验证

## 飞书群

- Webhook: `https://open.feishu.cn/open-apis/bot/v2/hook/6ef37044-4824-483b-a83e-fcd266554f71`

## Claude Code Hooks (settings.json)

```json
{
  "PostToolUse": [{"matcher": "Bash|Edit|Write", "hooks": [{"type": "command", "command": "bash ~/agent-workforce/hooks/auto_trace.sh", "timeout": 5, "async": true}]}],
  "Stop": [{"hooks": [{"type": "command", "command": "bash ~/agent-workforce/hooks/session_stop_trace.sh", "timeout": 10}]}],
  "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "bash ~/agent-workforce/hooks/capture_goal.sh", "timeout": 3, "async": true}]}],
  "SessionStart": [{"hooks": [{"type": "command", "command": "bash ~/agent-workforce/hooks/session_start.sh", "timeout": 3}]}]
}
```

## 目录结构

```
~/agent-workforce/
├── profiles/                     # 7 个 Agent Profile (YAML, 版本化)
│   ├── orchestrator/v1.0.yaml
│   ├── ios_agent/v1.0.yaml
│   ├── backend_agent/v1.0.yaml
│   ├── web_agent/v1.0.yaml
│   ├── data_agent/v1.0.yaml
│   ├── infra_agent/v1.0.yaml
│   └── reviewer/v1.0.yaml
├── rules/enforcement.yaml        # P0-P3 行为规则
├── traces/                       # 本地 JSONL (按日分片)
├── artifacts/                    # 产物注册表
├── knowledge/                    # 进化知识库
│   ├── failure_patterns/
│   │   └── bootstrap_lessons.md  # 创建过程学到的教训
│   ├── routing_rules/
│   │   └── learned_from_bootstrap.md
│   └── benchmark/
├── evolution/nightly_eval.py     # 夜间评测引擎
├── scripts/
│   ├── trace_schema.py           # Trace 数据结构 + auto_score
│   ├── envelope.py               # Task Envelope + Artifact Registry
│   └── feishu_notify.py          # 飞书通知
├── hooks/
│   ├── auto_trace.sh             # PostToolUse hook
│   ├── session_stop_trace.sh     # Stop hook (汇总 + 双写 + 飞书)
│   ├── capture_goal.sh           # UserPromptSubmit hook
│   ├── session_start.sh          # SessionStart hook
│   └── claude_code_hook.sh       # Shell 快捷命令
├── server/
│   ├── app.py                    # FastAPI 服务端
│   ├── requirements.txt
│   └── deploy.sh
├── config.yaml                   # 全局配置
├── cli.py                        # CLI 入口
├── CONTEXT.md                    # 本文件
├── README.md                     # 项目文档
└── docs/USER_GUIDE.md            # 使用指南
```

## 用户偏好 (从创建过程中学到的)

1. **先调研后决策** — 不接受直接给方案，需要看到调研过程和决策依据
2. **反馈极低摩擦** — 80% 场景零操作，最多按一个按钮
3. **安全边界敏感** — 部署/新增Agent/规则修改必须人类确认
4. **不要刷屏** — 只推重要的通知，小任务静默记录
5. **先想场景再写代码** — 每个任务先列用户场景和测试 case，完成后回归
6. **系统要能自我迭代** — 调教过程本身也是数据，要记录下来
7. **避免数据丢失** — 双写 (本地 + 远程)

## 待办事项

1. ✅ 火山云安全组开放 9100 端口
2. ✅ 飞书按钮改为 URL 跳转类型
3. ⏳ ~/.zshrc 加 source 行
4. ⏳ 飞书群创建话题分区
5. ⏳ 积累 20+ traces 后配置夜间 cron job
6. ⏳ 修复 nginx 的 ugc_access 变量问题
7. ⏳ 飞书按钮点击后服务端确认页优化 (手机适配)
