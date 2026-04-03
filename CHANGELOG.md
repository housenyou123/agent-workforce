# Changelog

## V3.0 — 2026-04-03

**让 Claude Code 拥有长期记忆。**

这是一次从"日志收集工具"到"能学习的 Agent 系统"的质变。核心变化：Claude Code 的每次 session 不再是失忆的 — 它现在能记住过去的经验，知道哪些文件改过多少次，知道哪些操作模式是高效的，哪些是反模式。

### 对日常使用 Claude Code 的帮助

**以前**：每次开 Claude Code 都是一个刚入职的新人。你让它改 `shadowrocket.go`，它不知道这个文件已经被改过 11 次了；你让它排查 VPN 503，它不知道上次 503 的根因是路由冲突。

**现在**：新 session 打开后第一次工具调用，Claude 会自动收到类似这样的上下文：

```
## 相关经验 (自动注入)
- 核心文件: shadowrocket.go (修改 11 次)，改前先 Read 完整文件
- 503 排查顺序: nginx upstream → Go 服务进程 → iptables → 路由
- VPN 路由冲突核心: AllowedIPs 和 metric 决定流量走向

## 可用技能
- network-diagnose: 全链路排查流程
- golden-execution: 高效执行模式 (2.4 calls/file, 0 retry)
```

这意味着：
- **少犯重复错误** — 同一个文件不会再反复改 11 次
- **知道先做什么** — 排查有顺序，不盲目 trial-and-error
- **继承最佳实践** — golden trace 的高效模式被自动传承

### 重大变化

#### 1. 记忆注入闭环 (memory_inject.sh)

新增 `PreToolUse` hook，每个 session 第一次工具调用前自动注入：
- 按当前项目 + Agent 查询相关经验
- 从 SQLite FTS5 记忆库召回高 importance 的 lesson
- 从 knowledge/patterns/ 加载可用技能

**这是整个系统最关键的改变 — 从"被动记录"变成"主动指导"。**

#### 2. 长期记忆库 (memory_db.py)

全新的 SQLite 记忆系统：
- **FTS5 全文搜索** — `python3 memory_db.py search "VPN 503"` 毫秒级返回
- **时间衰减** — 长期不用的记忆自动降权，保持记忆库新鲜
- **Citation 验证** — 每条记忆附带文件引用，使用前可验证是否过时
- **Importance 评分** — 0.0-1.0 重要性排序，优先注入最重要的经验
- 当前: 79 条记忆，476KB

#### 3. 自动评分 v2 (auto_rate)

重写了评分逻辑，解决 93% 任务都被评为 "good" 的区分度问题：
- 加入**效率信号** — tool_call / files_modified 比率
- 放宽 **golden 条件** — 不再要求显式 build pass
- 收紧 **fine 条件** — retry + 低效率组合降级

效果: good 93% → 40%, golden 0% → 52%

#### 4. 三级路由

解决 44% 的 trace 被标记为 "unknown" 的问题：
- **Level 1**: 路径前缀匹配 (精确)
- **Level 2**: Session 继承 — 短指令沿用上一条的 project
- **Level 3**: 内容关键词推断 — 从 goal 文本推断项目

效果: unknown 44% → 25%

#### 5. NetOps Agent

从 Backend Agent 中分裂出网络运维专家：
- 覆盖: VPN 配置、网络诊断、AWS VPC、nginx/Caddy
- 8 条从 142 条 VPN trace 中提炼的 lesson
- 6 条 quality gate (改前记录状态、改后验证用户、有回滚方案)

#### 6. 文件边界检测

每条 trace 自动检查 Agent 是否越界修改了能力域外的文件：
- iOS Agent 改了 .py → 报警
- Web Agent 改了 .swift → 报警
- 发现: iOS Agent 越界最少 → golden 率 60% (最高)

**结论: 边界越清晰，Agent 表现越好。**

#### 7. 蒸馏管道

traces → YAML → SQLite → Obsidian 自动蒸馏链路：
- 每晚 23:30 自动运行 (macOS launchd)
- 从 trace 中提取: 核心文件、弱项信号、高效模式、边界警告
- 产出写入 knowledge/ 和 Obsidian vault (可视化浏览)

#### 8. Web Dashboard

对标 Multica.ai 的可视化面板：
- **Sidebar 布局** + Multica 配色系统 + 暗色模式
- **Dashboard 页** — 统计卡片 + Agent Performance + Session 聚合 Activity Feed
- **Agents 页** — 左右分栏, 热点文件 / 最近 trace / 绑定 Skills
- **Skills 页** — 14 个预填技能, 创建/删除 Modal
- **Memory 页** — FTS5 搜索 + type 过滤 + importance 排序
- **Trace 详情** — 点击 Activity 条目展开: Goal / Agent / 工具调用 / 文件修改 / 验证状态
- **SSE 实时推送** — 新 trace 自动出现, 无需刷新

后端: 13 个新 API (Skills CRUD / Activity / Memory / Agents / SSE)

#### 9. Skills 系统

14 个预填技能，覆盖全部 Agent：
- 通用: golden-execution, retry-chain-breaker, file-boundary-check
- 后端: fastapi-crud, go-service-modify
- 网络: network-diagnose, vpn-user-management
- 前端: react-dashboard-page
- iOS: swiftui-view-pattern
- 基础设施: deploy-volcengine, deploy-aws-ssm, trace-analysis

#### 10. 一键部署

```bash
bash scripts/deploy_v3.sh
```
自动: build 前端 → sync 后端/前端/scripts → restart → 5 端点健康检查

### 数据总览

| 指标 | 数值 |
|------|------|
| Traces | 665 条 |
| Memories | 79 条 (SQLite 476KB) |
| Skills | 14 个 |
| Agents | 6 个 (含新增 NetOps) |
| 知识文件 | 96 个 (YAML + MD) |
| 新增代码 | 10,252 行 |
| 测试用例 | 48 个 (34 evolution + 14 memory) |

### 文件变更

- 新增 52 个文件
- 修改 13 个文件
- 总计 10,252 行新增代码
