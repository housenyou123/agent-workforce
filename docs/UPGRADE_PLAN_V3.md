# Agent Workforce V3 — 对标 Multica 改进方案

## 定位差异

| 维度 | Multica | AW V3 (我们) |
|------|---------|-------------|
| 目标用户 | 2-10 人团队 | 1 人 + AI 编队 |
| 核心价值 | Agent 项目管理 | Agent 自进化 |
| Agent 运行 | Daemon 常驻 + 任务队列 | Claude Code hook + session |
| 前端 | Next.js 16 (重量级) | **Next.js 15 lite** (轻量) |
| 后端 | Go + PostgreSQL | **FastAPI + SQLite** (现有) |
| 实时通信 | WebSocket + Hub | **SSE (Server-Sent Events)** |

**我们不做 Multica 的全量复刻，而是取其精华补到我们的进化体系上。**

---

## 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                    AW V3 Web Dashboard                       │
│  Next.js (或 Vite) 前端                                      │
│                                                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐│
│  │ Activity │ │ Agents   │ │ Skills   │ │ Memory           ││
│  │ Feed     │ │ Board    │ │ Library  │ │ Explorer         ││
│  │ (时间线) │ │ (看板)   │ │ (技能库) │ │ (记忆检索)       ││
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────────────┘│
└───────┼────────────┼────────────┼─────────────┼──────────────┘
        │            │            │             │
  ──────┼────────────┼────────────┼─────────────┼────── API ────
        ▼            ▼            ▼             ▼
┌─────────────────────────────────────────────────────────────┐
│                 FastAPI Backend (V3)                          │
│                                                              │
│  /api/activity   — 统一时间线 (trace + 人工操作)              │
│  /api/agents     — Agent CRUD + 状态 + 统计                  │
│  /api/skills     — Skill CRUD + 绑定到 agent                 │
│  /api/memory     — 记忆查询/搜索/时间衰减                     │
│  /api/traces     — 原始 trace 数据 (现有)                     │
│  /api/stats      — Dashboard 统计 (现有)                      │
│  /api/feedback   — 反馈收集 (现有)                            │
│  /sse            — Server-Sent Events 实时推送                │
│                                                              │
│  SQLite: traces.db + memory.db                               │
└─────────────┬──────────────────────────────────┬─────────────┘
              │                                  │
    ┌─────────▼─────────┐              ┌─────────▼──────────┐
    │  Claude Code       │              │  Nightly Distill   │
    │  Hooks (现有)      │              │  (每晚 23:30)      │
    │  auto_trace.sh     │              │  traces → YAML     │
    │  session_stop.sh   │              │  → SQLite memory   │
    │  memory_inject.sh  │              │  → Obsidian vault  │
    └────────────────────┘              └────────────────────┘
```

---

## Phase 0: 后端 API 扩展 (Day 1-2)

**在现有 FastAPI app.py 上新增 4 组 API，不重写。**

### 0.1 Activity Feed API

```python
# GET /api/activity?date=2026-04-03&project=enterprise-vpn&limit=50
# 返回统一时间线: traces + 人工操作混排

@app.get("/api/activity")
async def activity_feed(
    date: str = None,        # 按日期筛选
    project: str = None,     # 按项目筛选  
    agent: str = None,       # 按 agent 筛选
    limit: int = 50,
):
    # 从 traces 表 + activity_log 表合并
    # 按 timestamp DESC 排序
    # 返回: [{type, timestamp, actor, project, summary, auto_feedback, ...}]
```

### 0.2 Skills API

```python
# 新增 skills 表
CREATE TABLE skills (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    content TEXT NOT NULL,       -- Skill 指令内容 (markdown)
    projects TEXT DEFAULT '[]',  -- 绑定的项目 (JSON array)
    agents TEXT DEFAULT '[]',    -- 绑定的 agent (JSON array)
    triggers TEXT DEFAULT '[]',  -- 触发条件 (JSON array)
    source_traces TEXT DEFAULT '[]', -- 来源 trace
    created_at TEXT,
    updated_at TEXT,
    usage_count INTEGER DEFAULT 0,
);

# CRUD
POST   /api/skills           — 创建 skill
GET    /api/skills            — 列表 (支持 project/agent 筛选)
GET    /api/skills/{id}       — 详情
PUT    /api/skills/{id}       — 更新
DELETE /api/skills/{id}       — 删除
POST   /api/skills/{id}/bind  — 绑定到 project/agent
```

### 0.3 Memory API

```python
# 复用现有 memory.db，暴露为 HTTP API
GET /api/memory/search?q=VPN+503           — FTS 搜索
GET /api/memory/recall?project=xxx&agent=x — 按维度召回
GET /api/memory/stats                      — 统计
POST /api/memory/decay                     — 手动触发衰减
```

### 0.4 Agent 增强 API

```python
# 增强现有 /api/stats，加入 agent 详情页
GET /api/agents                            — 列表 (含统计)
GET /api/agents/{id}                       — 详情 + 技能 + 记忆 + 最近 traces
GET /api/agents/{id}/skills                — agent 绑定的 skills
GET /api/agents/{id}/timeline              — agent 个人时间线
```

### 0.5 SSE 实时推送 (替代 WebSocket)

```python
# 比 WebSocket 简单得多，单向推送足够
# 前端用 EventSource API 接收

@app.get("/sse")
async def sse_stream():
    async def event_generator():
        while True:
            # 检查新 trace / feedback / skill 变更
            event = await check_updates()
            if event:
                yield f"data: {json.dumps(event)}\n\n"
            await asyncio.sleep(3)
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

---

## Phase 1: Skills 系统 (Day 2-3)

**从 Multica 借鉴但适配到我们的 hook 体系。**

### 1.1 Skill 定义格式

```markdown
<!-- skills/deploy-vpn.md -->
---
name: deploy-vpn
description: VPN 服务部署到火山云
projects: [enterprise-vpn]
agents: [netops_agent, backend_agent]
triggers:
  - keyword: "部署"
  - keyword: "上线"
  - keyword: "deploy"
---

## 部署前检查
1. 确认当前 VPN 用户连接状态: `wg show`
2. 备份当前配置: `cp /etc/wireguard/wg0.conf /etc/wireguard/wg0.conf.bak.$(date +%s)`
3. 检查 git status 确认变更内容

## 部署步骤
1. `go build -o vpn-server ./cmd/server`
2. `scp vpn-server root@118.196.147.14:/opt/enterprise-vpn/`
3. `ssh root@118.196.147.14 "systemctl restart vpn-server"`

## 部署后验证
1. `curl -sf http://118.196.147.14:9090/health`
2. 检查所有用户连接: `ssh root@118.196.147.14 "wg show"`
3. 验证 Shadowrocket 订阅: 重新拉取一次确认格式

## 回滚
如果部署失败:
1. `ssh root@118.196.147.14 "cp /opt/enterprise-vpn/vpn-server.bak /opt/enterprise-vpn/vpn-server && systemctl restart vpn-server"`
```

### 1.2 Skill 注入机制

在现有 `memory_inject.sh` 中增加 skill 注入:

```bash
# 检测当前 project → 查询绑定的 skills → 注入到 systemMessage
SKILLS=$(python3 -c "
from memory_db import MemoryDB
db = MemoryDB()
# 按 project 查询绑定的 skills
skills = db.recall(project='$PROJECT', type='skill', limit=3)
print(db.format_for_injection(skills, max_chars=2000))
")
```

### 1.3 Skill 自动生成

从 golden trace 中自动提取 skill:

```python
# 在 distill_knowledge.py 中新增:
def extract_skills_from_golden(traces):
    """从 golden trace 提取可复用的操作步骤"""
    # 找出重复出现的 tool_call 序列
    # 如果同一个操作序列在 3+ 个 golden trace 中出现 → 封装为 skill
```

---

## Phase 2: 前端 Dashboard (Day 3-5)

**用 Vite + React 构建，对标 Multica 的关键页面但大幅简化。**

### 2.1 技术选型

```
Vite + React 19 + TypeScript
Tailwind CSS v4
shadcn/ui 组件库
Recharts (图表)
EventSource API (SSE)
```

**不用 Next.js** — 我们是纯 SPA，不需要 SSR，Vite 更轻。

### 2.2 页面设计 (4 个页面)

#### Page 1: Dashboard (首页)

```
┌─────────────────────────────────────────────────┐
│  Agent Workforce                    [今天 4/3]   │
├─────────────────────────────────────────────────┤
│                                                  │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐           │
│  │ 174  │ │  52% │ │ $2.1 │ │  25% │           │
│  │Tasks │ │Golden│ │ Cost │ │ Unkn │           │
│  └──────┘ └──────┘ └──────┘ └──────┘           │
│                                                  │
│  ── Activity Feed ──────────────────────────────│
│  │ 14:35 [netops] enterprise-vpn                │
│  │   修改 shadowrocket.go (编辑 2 处) ⭐ golden │
│  │                                              │
│  │ 14:21 [backend] interview-bot                │
│  │   修改 events.py, client.py (编辑 4 处) 👍   │
│  │                                              │
│  │ 13:58 [web] spot-playground                  │
│  │   执行: 网络检查 (6 条命令) ⚠️ fine          │
│  └──────────────────────────────────────────────│
│                                                  │
│  ── Agent Performance ──────────────────────────│
│  │ Agent          Tasks  Golden%  Cost  Trend   │
│  │ backend_agent   295    51%    $3.2    ↗     │
│  │ netops_agent     14    57%    $0.4    →     │
│  │ infra_agent      90    50%    $1.1    ↘     │
│  └──────────────────────────────────────────────│
└─────────────────────────────────────────────────┘
```

#### Page 2: Agents (Agent 详情看板)

```
┌─────────────────────────────────────────────────┐
│  Agents                                          │
├──────────────┬──────────────────────────────────┤
│              │                                   │
│  Agents      │  ── NetOps Agent ──               │
│  ──────      │  Model: sonnet  Status: idle      │
│  ● backend   │                                   │
│  ● netops ←  │  Stats (7d): 14 tasks, 57% gold  │
│  ● infra     │  Violations: 2                    │
│  ● web       │                                   │
│  ● ios       │  ── Skills (3) ──                 │
│  ● data      │  📋 deploy-vpn                    │
│              │  📋 network-diagnose              │
│              │  📋 shadowrocket-config            │
│              │                                   │
│              │  ── Hot Files ──                   │
│              │  shadowrocket.go (11x)            │
│              │  memory.go (4x)                   │
│              │                                   │
│              │  ── Recent Traces ──               │
│              │  [tr_042] 修改 shadow... ⭐        │
│              │  [tr_041] 网络检查 6cmd 👍        │
└──────────────┴──────────────────────────────────┘
```

#### Page 3: Skills (技能库)

```
┌─────────────────────────────────────────────────┐
│  Skills Library                    [+ New Skill] │
├─────────────────────────────────────────────────┤
│                                                  │
│  ┌─────────────────────────────────────────────┐│
│  │ 📋 deploy-vpn                               ││
│  │ VPN 服务部署到火山云                         ││
│  │ Agents: netops_agent, backend_agent          ││
│  │ Used: 8 times  |  Source: 3 golden traces    ││
│  └─────────────────────────────────────────────┘│
│                                                  │
│  ┌─────────────────────────────────────────────┐│
│  │ 📋 network-diagnose                         ││
│  │ 网络问题全链路排查                           ││
│  │ Agents: netops_agent                         ││
│  │ Used: 12 times  |  Anti-pattern: retry_chain ││
│  └─────────────────────────────────────────────┘│
│                                                  │
│  ┌─────────────────────────────────────────────┐│
│  │ 📋 golden-execution (auto-generated)        ││
│  │ 从 120 条 golden trace 提炼的高效执行模式    ││
│  │ Agents: ALL                                  ││
│  │ Avg: 2.4 calls/file  |  0 retry              ││
│  └─────────────────────────────────────────────┘│
└─────────────────────────────────────────────────┘
```

#### Page 4: Memory (记忆检索)

```
┌─────────────────────────────────────────────────┐
│  Memory Explorer               [71 memories]     │
├─────────────────────────────────────────────────┤
│                                                  │
│  Search: [VPN 503________________] [🔍 Search]   │
│                                                  │
│  Filters:  [All Types ▼] [All Projects ▼]       │
│                                                  │
│  Results (6):                                    │
│  ┌──────────────────────────────────────────────┐│
│  │ ★0.9 [lesson] enterprise-vpn                 ││
│  │ 核心文件: shadowrocket.go (修改 11 次)        ││
│  │ 修改前务必 Read 完整文件理解上下文             ││
│  │ Accessed: 5 times  |  Last: 2h ago            ││
│  ├──────────────────────────────────────────────┤│
│  │ ★0.8 [pattern] retry_chains                  ││
│  │ 重试链反模式: 用户说"还是不行"超过2次时       ││
│  │ 应停下来先画拓扑...                           ││
│  └──────────────────────────────────────────────┘│
│                                                  │
│  ── Importance Distribution ────────────────────│
│  │ ★0.9+ ████████ 12                            │
│  │ ★0.7+ ██████████████████████ 38              │
│  │ ★0.5+ ████████████████████████████ 71        │
│  └──────────────────────────────────────────────│
└─────────────────────────────────────────────────┘
```

---

## Phase 3: 前后端联调 + SSE (Day 5-6)

### 3.1 前端 API Client

```typescript
// src/api/client.ts
const API = import.meta.env.VITE_API_URL || 'http://118.196.147.14/aw';

export const api = {
  // Activity
  activity: (params) => fetch(`${API}/api/activity?${qs(params)}`),
  
  // Agents
  agents: () => fetch(`${API}/api/agents`),
  agent: (id) => fetch(`${API}/api/agents/${id}`),
  
  // Skills
  skills: () => fetch(`${API}/api/skills`),
  createSkill: (data) => fetch(`${API}/api/skills`, { method: 'POST', body: JSON.stringify(data) }),
  
  // Memory
  searchMemory: (q) => fetch(`${API}/api/memory/search?q=${q}`),
  recallMemory: (project, agent) => fetch(`${API}/api/memory/recall?project=${project}&agent=${agent}`),
  
  // Dashboard
  stats: (days) => fetch(`${API}/api/stats?days=${days}`),
  traces: (params) => fetch(`${API}/api/traces?${qs(params)}`),
};
```

### 3.2 SSE 实时更新

```typescript
// src/hooks/useSSE.ts
export function useSSE() {
  useEffect(() => {
    const es = new EventSource(`${API}/sse`);
    es.onmessage = (e) => {
      const event = JSON.parse(e.data);
      // 更新对应的 Zustand store
      if (event.type === 'trace:new') activityStore.addTrace(event.data);
      if (event.type === 'feedback:new') activityStore.updateFeedback(event.data);
    };
    return () => es.close();
  }, []);
}
```

---

## Phase 4: Skills 自动化 + 注入闭环 (Day 6-7)

### 4.1 从 trace 自动生成 skill 候选

```python
# evolution/auto_skill.py
def suggest_skills(traces):
    """从 golden traces 中发现可复用的操作模式"""
    
    # 1. 找重复出现的 tool_call 序列
    # 2. 聚类相似的 goal (VPN部署、网络排查等)
    # 3. 生成 skill 草稿 → 推飞书等人工确认
    
    # 输出: skills/draft/xxx.md
    # 人工确认后 mv 到 skills/active/
```

### 4.2 完整注入闭环

```
Session 开始
  ↓ memory_inject.sh
  ↓ detect_scenario() → project, agent
  ↓ query memory.db: recall(project, agent)
  ↓ query skills: by project + by agent
  ↓ format: lessons + skills → systemMessage
  ↓
Claude Code 收到:
  "## 相关经验
   - shadowrocket.go 修改过 11 次，先 Read 完整文件
   - VPN 重试链模式: 先画拓扑再动手
   ## 可用技能
   - deploy-vpn: 部署步骤见下方
   - network-diagnose: 全链路排查流程"
  ↓
Session 执行 → trace 记录
  ↓
Nightly distill:
  - 蒸馏新 lessons
  - 更新 skills usage_count
  - 发现新 skill 候选
  - 时间衰减旧记忆
  ↓
次日 Session 注入更新后的记忆 + 技能
```

---

## 实施时间线

| Day | 内容 | 产出 |
|-----|------|------|
| **1** | 后端: Skills 表 + CRUD API + Memory API | app.py 扩展 |
| **2** | 后端: Activity Feed API + Agent 详情 API + SSE | 完整 API 层 |
| **3** | 前端: Vite 项目初始化 + Dashboard 页 | 首页可看 |
| **4** | 前端: Agents 页 + Skills 页 | Agent 看板 |
| **5** | 前端: Memory Explorer + SSE 联调 | 记忆检索 |
| **6** | Skills 注入: memory_inject.sh 增加 skill 注入 | 闭环 |
| **7** | 部署到火山云 + Caddy 反代 | 线上可用 |

## 技术决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 前端框架 | Vite + React | 比 Next.js 轻，纯 SPA 够用 |
| 组件库 | shadcn/ui + Tailwind | 快速出 UI |
| 实时通信 | SSE (非 WebSocket) | 单向推送足够，代码量少 80% |
| 数据库 | SQLite (非 PostgreSQL) | 单用户场景，零运维 |
| Agent 运行 | Hook 模式 (非 Daemon) | 贴着 Claude Code 原生能力 |
| 前端部署 | 静态文件 + Caddy | `caddy file-server` 一行搞定 |

## 不做的事

- ❌ 不做用户认证 (单用户系统)
- ❌ 不做 Daemon 常驻进程 (hook 模式已够)
- ❌ 不做多 Workspace (只有一个工作区)
- ❌ 不做 Issue 系统 (trace 即是任务记录)
- ❌ 不做文件上传 (S3 等)
- ❌ 不做 WebSocket Hub (SSE 单向推送)
