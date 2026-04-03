# Agent Workforce — 安装指南

> 让 Claude Code 有长期记忆的 AI Agent 协作系统。
> 自动采集 trace → 评分 → 蒸馏 → 记忆注入 → 下次 session 更聪明。

## 5 分钟快速开始

### 1. 克隆项目

```bash
git clone https://github.com/housenyou123/agent-workforce.git ~/agent-workforce
cd ~/agent-workforce
```

### 2. 配置文件

```bash
cp config.example.yaml config.yaml
# 编辑 config.yaml，填入你的:
# - 飞书 webhook URL (可选，不配则不推送通知)
# - 服务器 IP (如果需要远程 Dashboard)
```

### 3. 配置 project_routes

编辑 `config.yaml` 中的 `project_routes`，把路径改成你自己的项目目录：

```yaml
project_routes:
  "your-project-dir": {project: "my-project", scenario: "backend_api", agent: "backend_agent"}
```

### 4. 安装 Claude Code Hooks

编辑 `~/.claude/settings.json`，在 `hooks` 中添加：

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "hooks": [
          {
            "async": true,
            "command": "bash ~/agent-workforce/hooks/auto_trace.sh",
            "timeout": 5,
            "type": "command"
          }
        ],
        "matcher": "Bash|Edit|Write|Read"
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "command": "bash ~/agent-workforce/hooks/session_stop_trace.sh",
            "statusMessage": "Saving trace...",
            "timeout": 10,
            "type": "command"
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "hooks": [
          {
            "command": "bash ~/agent-workforce/hooks/memory_inject.sh",
            "timeout": 5,
            "type": "command"
          }
        ],
        "matcher": "*"
      }
    ]
  }
}
```

合并到你现有的 settings.json 中（不要替换，要合并 hooks 数组）。

### 5. 初始化记忆库

```bash
# 创建 traces 目录
mkdir -p ~/agent-workforce/traces

# 首次蒸馏（如果已有 trace 数据）
python3 ~/agent-workforce/evolution/distill_knowledge.py --apply
```

### 6. 验证

开一个新的 Claude Code session，执行任意工具调用，你应该看到：
- `PreToolUse:Read says: ## 相关经验 (自动注入)` — 记忆注入
- `Stop says: [aw] tr_xxx traced | auto: 3/good` — trace 采集 + 评分

---

## 系统架构

```
Claude Code Session
  ↓ auto_trace.sh (PostToolUse)    ← 记录每次工具调用
  ↓ session_stop_trace.sh (Stop)   ← session 结束时汇总 + 评分
  ↓ memory_inject.sh (PreToolUse)  ← session 开始时注入记忆
  ↓
traces/YYYY-MM-DD.jsonl            ← 原始 trace 数据
  ↓
distill_knowledge.py               ← 蒸馏: traces → YAML + SQLite
  ↓
knowledge/
  ├── agents/*.yaml                ← Agent 能力档案
  ├── projects/*.yaml              ← 项目经验
  ├── patterns/*.yaml              ← 模式库 (成功/失败)
  └── memory.db                    ← SQLite FTS5 可查询记忆库
```

## 功能说明

### 自动 Trace 采集 (零配置)

每次 Claude Code session 结束时自动记录：
- 用了哪些工具、改了哪些文件
- 对话轮次、持续时间、token 消耗
- 自动评分 (1-4: bad/fine/good/golden)

### 三级路由

自动识别当前任务属于哪个项目、哪个 Agent：
1. **路径匹配** — `config.yaml` 中的 `project_routes`
2. **Session 继承** — 短指令沿用上一条的项目
3. **内容推断** — 从 goal 关键词推断

### 记忆注入

每个新 session 的第一次工具调用前，自动注入：
- **相关经验** — 该项目/Agent 的历史教训
- **可用技能** — 可复用的操作流程

### 自动评分 (auto_rate v2)

| 评分 | 条件 |
|------|------|
| 1 bad | build 失败 / 凭据泄露 / 越界 |
| 2 fine | retry > 2 / rounds > 5 / 低效 |
| 3 good | 默认 |
| 4 golden | 高效完成 (效率比 ≤ 5, 无 retry) |

### 记忆蒸馏

```bash
# 手动蒸馏
python3 ~/agent-workforce/evolution/distill_knowledge.py --apply

# 查询记忆
python3 ~/agent-workforce/scripts/memory_db.py search "关键词"
python3 ~/agent-workforce/scripts/memory_db.py recall --project my-project

# 回补历史 trace
python3 ~/agent-workforce/scripts/recalc_traces.py --apply
```

### 自动蒸馏 (macOS launchd)

```bash
# 安装每晚 23:30 自动蒸馏
cp scripts/com.agent-workforce.nightly-distill.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.agent-workforce.nightly-distill.plist
```

---

## Web Dashboard (可选)

### 本地开发

```bash
cd ~/agent-workforce/dashboard
npm install
npm run dev
# 打开 http://localhost:5173
```

### 部署到服务器

1. 编辑 `server/app.py` 中的数据库路径
2. `pip install fastapi uvicorn`
3. `uvicorn app:app --host 0.0.0.0 --port 9100`
4. 用 Nginx/Caddy 反代

Dashboard 功能: Activity Feed (session 聚合) / Agent 详情 / Skills 管理 / Memory 搜索

---

## Agent Profiles

系统内置 6 个 Agent Profile：

| Agent | 覆盖 |
|-------|------|
| backend_agent | Python/Go/TS 后端 |
| netops_agent | VPN/网络诊断/云网络 |
| web_agent | React/Next.js 前端 |
| ios_agent | Swift/SwiftUI |
| infra_agent | 脚本/CI/配置 |
| data_agent | 数据分析/ML |

自定义: 在 `profiles/` 下创建新目录 + `v1.0.yaml`，参考现有 profile 格式。

在 `config.yaml` 的 `project_routes` 中配置路由到你的 Agent。

---

## 自定义

### 添加新项目

1. `config.yaml` → `project_routes` 添加路径映射
2. `scripts/trace_schema.py` → `_CONTENT_KEYWORDS` 添加关键词 (可选)
3. 正常使用，trace 会自动积累

### 添加新 Agent

1. `profiles/my_agent/v1.0.yaml` — 参考现有格式
2. `config.yaml` → `model_allocation` 添加模型分配
3. `config.yaml` → `project_routes` 中引用新 agent

### 添加记忆

```python
from memory_db import MemoryDB
db = MemoryDB()
db.save("lesson", content="重要经验...", project="my-project", agent="my_agent", importance=0.8)
db.close()
```

---

## 要求

- Python 3.11+
- Claude Code CLI
- Node.js 18+ (仅 Dashboard)
- macOS (launchd 定时任务) 或 Linux (改用 cron)
