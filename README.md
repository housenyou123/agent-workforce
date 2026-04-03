# Agent Workforce

**让 Claude Code 拥有长期记忆的开源系统。**

每次 session 自动采集经验 → 评分 → 蒸馏 → 下次 session 注入 → Agent 越用越聪明。

## 解决什么问题

Claude Code 每次对话都是失忆的。你昨天让它改了 `shadowrocket.go` 11 次才改对，今天它完全不记得。

Agent Workforce 在 Claude Code 的 hooks 上构建了一个闭环：

```
开始 session → 自动注入历史经验和技能
      ↓
正常工作 (零感知采集 trace)
      ↓
结束 session → 自动评分 (golden/good/fine/bad)
      ↓
每晚蒸馏 → 更新记忆库
      ↓
次日 session → 注入更新后的记忆
```

## 效果

实际数据 (665 条 trace)：

| 指标 | 说明 |
|------|------|
| 自动评分 | 100% 覆盖，无需手动打分 |
| 项目识别 | 75% 自动路由到正确 Agent |
| 边界检测 | 36 次越界被检出 |
| 记忆注入 | session 开始时自动注入相关经验 |

## 5 分钟安装

```bash
git clone https://github.com/housenyou123/agent-workforce.git ~/agent-workforce
cp ~/agent-workforce/config.example.yaml ~/agent-workforce/config.yaml
```

编辑 `config.yaml`，把 `project_routes` 改成你的项目路径：

```yaml
project_routes:
  "my-project-dir": {project: "my-project", scenario: "backend_api", agent: "backend_agent"}
```

然后在 `~/.claude/settings.json` 的 `hooks` 中添加 (合并到现有配置，不要替换)：

```json
{
  "PostToolUse": [{
    "hooks": [{"async": true, "command": "bash ~/agent-workforce/hooks/auto_trace.sh", "timeout": 5, "type": "command"}],
    "matcher": "Bash|Edit|Write|Read"
  }],
  "Stop": [{
    "hooks": [{"command": "bash ~/agent-workforce/hooks/session_stop_trace.sh", "timeout": 10, "type": "command"}]
  }],
  "PreToolUse": [{
    "hooks": [{"command": "bash ~/agent-workforce/hooks/memory_inject.sh", "timeout": 5, "type": "command"}],
    "matcher": "*"
  }]
}
```

开一个新的 Claude Code session，发一句话，你会看到：
- `PreToolUse says: ## 相关经验 (自动注入)` — 记忆注入生效
- `Stop says: [aw] tr_xxx traced | auto: 3/good` — trace 采集 + 评分生效

详细安装说明见 [SETUP.md](SETUP.md)。

## 架构

```
~/.claude/settings.json (hooks 配置)
      ↓
┌─────────────────────────────────────────────────┐
│ Claude Code Hooks                                │
│  auto_trace.sh     → 记录每次工具调用            │
│  session_stop.sh   → 汇总 + auto_rate 评分       │
│  memory_inject.sh  → 注入记忆 + 技能             │
└────────────┬────────────────────────┬────────────┘
             ↓                        ↓
    traces/YYYY-MM-DD.jsonl    knowledge/memory.db
    (原始 trace 数据)           (FTS5 可查询记忆库)
             ↓
    distill_knowledge.py (蒸馏)
             ↓
    knowledge/
    ├── agents/*.yaml      (Agent 能力档案)
    ├── projects/*.yaml    (项目经验沉淀)
    └── patterns/*.yaml    (成功/失败模式库)
```

## 核心功能

### 1. 自动 Trace 采集
每次 session 结束自动记录：工具调用、文件修改、对话轮次、持续时间、token 消耗。零配置，零感知。

### 2. 自动评分 (auto_rate v2)
| 评分 | 条件 |
|------|------|
| golden (4) | 高效完成 — 效率比 ≤ 5，无 retry |
| good (3) | 正常完成 |
| fine (2) | 有挣扎 — retry > 2 或 rounds > 5 |
| bad (1) | 失败 — build 失败 / 凭据泄露 / 越界 |

### 3. 三级路由
自动识别当前 session 属于哪个项目/Agent：
1. **路径匹配** — `config.yaml` 中的 `project_routes`
2. **Session 继承** — 短指令沿用上一条的项目
3. **内容推断** — 从 goal 关键词推断

### 4. 记忆注入
每个新 session 的第一次工具调用前自动注入：
- **相关经验** — 该项目的核心文件、历史教训
- **可用技能** — 可复用的操作流程 (排查步骤、部署流程等)

### 5. 文件边界检测
自动检查 Agent 是否修改了能力域外的文件 (比如 web_agent 改了 .swift 文件)。

### 6. 记忆蒸馏
从 trace 中提取可复用的经验，存入 SQLite FTS5 数据库：
```bash
python3 ~/agent-workforce/evolution/distill_knowledge.py --apply
python3 ~/agent-workforce/scripts/memory_db.py search "VPN 503"
```

## Agent 编队

| Agent | 覆盖 | 说明 |
|-------|------|------|
| backend_agent | Python/Go/TS 后端 | API 开发、数据库、AI 编排 |
| netops_agent | VPN/网络/云 | 网络诊断、路由配置、部署 |
| web_agent | React/Next.js | 前端 UI、Dashboard |
| ios_agent | Swift/SwiftUI | Apple 原生开发 |
| infra_agent | 脚本/CI/配置 | hooks、trace 系统、自动化 |
| data_agent | 数据分析/ML | UGC 分析、VLM 评估 |

自定义 Agent: 在 `profiles/` 下创建新目录 + `v1.0.yaml`。

## Web Dashboard (可选)

Multica 风格的可视化面板：

```bash
cd ~/agent-workforce/dashboard
npm install && npm run dev
```

功能: Activity Feed (session 聚合) / Agent 详情 / Skills 管理 / Memory 搜索 / 暗色模式

## 常用命令

```bash
# 查看今天的 trace
cat ~/agent-workforce/traces/$(date +%Y-%m-%d).jsonl | python3 -c "import sys,json; [print(json.loads(l).get('summary','')[:60]) for l in sys.stdin]"

# 搜索记忆
python3 ~/agent-workforce/scripts/memory_db.py search "关键词"

# 按项目召回记忆
python3 ~/agent-workforce/scripts/memory_db.py recall --project my-project

# 蒸馏
python3 ~/agent-workforce/evolution/distill_knowledge.py --apply

# 回补历史 trace (路由 + 评分 + 边界检测)
python3 ~/agent-workforce/scripts/recalc_traces.py --apply

# 记忆库统计
python3 ~/agent-workforce/scripts/memory_db.py stats
```

## 目录结构

```
agent-workforce/
├── hooks/                  # Claude Code hooks (核心)
│   ├── auto_trace.sh       #   PostToolUse: 记录工具调用
│   ├── session_stop_trace.sh #  Stop: 汇总 + 评分
│   └── memory_inject.sh    #   PreToolUse: 注入记忆
├── scripts/                # 核心逻辑
│   ├── trace_schema.py     #   Trace 数据结构 + 三级路由
│   ├── trace_engine.py     #   auto_rate + 边界检测 + 处理
│   ├── memory_db.py        #   SQLite 记忆库 (FTS5)
│   └── recalc_traces.py    #   历史 trace 回补
├── evolution/              # 蒸馏 + 评测
│   ├── distill_knowledge.py #  traces → YAML + SQLite
│   └── nightly_eval.py     #  夜间评测引擎
├── profiles/               # Agent Profile (YAML)
├── knowledge/              # 蒸馏产物
│   ├── agents/*.yaml       #   Agent 能力档案
│   ├── projects/*.yaml     #   项目经验
│   └── patterns/*.yaml     #   模式库
├── dashboard/              # Web Dashboard (Vite + React)
├── server/                 # FastAPI 后端
├── config.yaml             # 项目路由 + 配置
└── docs/                   # 设计文档
```

## 技术栈

- **Hooks**: Bash + Python (零依赖)
- **存储**: SQLite FTS5 (记忆) + JSONL (trace)
- **前端**: Vite + React + Tailwind v4
- **后端**: FastAPI + SQLite
- **部署**: PM2 + Caddy (可选)

## 要求

- Python 3.11+
- Claude Code CLI
- Node.js 18+ (仅 Dashboard)

## License

MIT
