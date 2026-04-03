# Long-Term Memory 设计方案

## 问题

trace 是流水账（541+ 条 JSONL），Claude Memory 是快照（29 个 md），中间缺一个"蒸馏→沉淀→检索"层。

trace 数据有价值但不可直接消费：
- 太大（1.1MB+，持续增长）
- 太细（每次工具调用一条记录）
- 无结构（关键洞察淹没在噪声中）

## 三层记忆架构

```
┌─────────────────────────────────────────┐
│  Layer 3: Claude Memory (索引+快照)      │  ~/.claude/.../memory/
│  - MEMORY.md 索引                       │  每条 <150 字
│  - project_*.md 项目快照                 │  AI 每次对话自动加载
│  - feedback_*.md 行为反馈                │  手工 + AI 协作维护
└────────────────────┬────────────────────┘
                     │ 引用
┌────────────────────▼────────────────────┐
│  Layer 2: Knowledge Base (蒸馏沉淀)      │  ~/agent-workforce/knowledge/
│  - agents/  Agent 能力档案              │  从 trace 自动蒸馏
│  - projects/ 项目经验沉淀               │  按周/月更新
│  - patterns/ 模式库 (成功/失败)          │  可被 CLAUDE.md 引用
│  - decisions/ 架构决策记录               │  人工确认后写入
│  - workflows/ 工作流最佳实践             │  从 golden trace 提炼
└────────────────────┬────────────────────┘
                     │ 蒸馏自
┌────────────────────▼────────────────────┐
│  Layer 1: Traces (原始流水)              │  ~/agent-workforce/traces/
│  - YYYY-MM-DD.jsonl 日志                │  hook 自动写入
│  - 含 auto_feedback / quality_score      │  不可直接消费
│  - 含 boundary_violations               │  只在蒸馏时读取
└─────────────────────────────────────────┘
```

## Layer 2 详细设计

### knowledge/agents/ — Agent 能力档案

每个 agent 一个自动更新的能力档案，从 trace 蒸馏而非手写。

```yaml
# knowledge/agents/backend_agent.yaml
agent: backend_agent
last_updated: 2026-04-02
total_tasks: 280
scores:
  golden_rate: 51%
  bad_rate: 1%
  boundary_violations: 13
strengths:              # 从 golden traces 提炼
  - "Go 网络服务开发 (shadowrocket.go 11次修改，最终稳定)"
  - "Python 后端 API (FastAPI, events.py)"
weaknesses:             # 从 bad/fine traces 提炼
  - "网络诊断效率低 (已分离到 netops_agent)"
  - "跨文件依赖分析不足 (ecosystem.config.cjs 反复改)"
hot_files:              # 高频修改文件
  - shadowrocket.go: 11
  - render_test.go: 6
  - events.py: 24
lessons:                # 从 retry 链提炼
  - "改 Go 路由配置前先读完整个 handler 链"
  - "多组件联动先画数据流"
```

### knowledge/projects/ — 项目经验沉淀

每个活跃项目一个经验文件，比 Claude Memory 的 project_*.md 更详细。

```yaml
# knowledge/projects/enterprise-vpn.yaml
project: enterprise-vpn
last_updated: 2026-04-02
total_tasks: 156
health:
  golden_rate: 56%
  retry_chains: 8   # 长重试链数
  avg_chain_len: 5.5
architecture:
  stack: "Go + WireGuard + Xray + nginx"
  deploy: "火山云 118.196.147.14:9090"
  critical_files:
    - shadowrocket.go   # 订阅生成核心
    - memory.go          # 内存缓存
    - setup.go           # 初始化配置
known_pitfalls:
  - "503 排查: nginx upstream → 服务进程 → iptables → 路由"
  - "内网 VPN 路由优先级: AllowedIPs + metric"
  - "大文件传输: HK 中转 vs 直连的带宽差异"
resolved_issues:        # 从 trace 链提取
  - date: 2026-03-26
    issue: "VPN 开启后内网服务 503"
    root_cause: "路由冲突，AllowedIPs 覆盖了内网网段"
    fix: "拆分路由规则，内网走 S2S 直连"
```

### knowledge/patterns/ — 模式库

从 trace 中提取的可复用模式（成功模式 + 反模式）。

```yaml
# knowledge/patterns/network_debugging.yaml
pattern: network_debugging
type: workflow  # workflow / anti-pattern / decision
source: "VPN traces 分析 (156 tasks, 8 retry chains)"

description: |
  网络排查的有效顺序，从 golden traces 中提炼。

steps:
  1. 画拓扑 (ASCII 或描述每一跳的协议/端口)
  2. 记录 before 状态 (ip route + iptables + ss -tlnp)
  3. 定位断点 (从 client → server 逐跳 ping/curl)
  4. 单点修复 + 验证套件 (不是改一个试一个)
  5. 确认不影响现有用户

anti_patterns:
  - name: "试一试循环"
    signal: "用户说'再试试'/'还是不行' 超过 2 次"
    fix: "停下来，先画拓扑，定位具体断点"
  - name: "盲改配置"
    signal: "同一文件修改 3+ 次且中间有 retry"
    fix: "Read 完整文件 + 理解调用链 + 一次性修复"
```

### knowledge/decisions/ — 架构决策记录 (ADR)

重要的技术/架构决策，human-confirmed。

```markdown
# knowledge/decisions/001-claude-native-not-runtime.md
# ADR-001: Claude-native 协作而非重型 runtime

## 状态: Accepted (2026-03-25)

## 上下文
需要选择 Agent 协作方式: 重型 runtime (LangGraph/CrewAI) vs Claude-native (hooks+trace+profile)

## 决策
选择 Claude-native: 以 Claude Code session 为最小执行单元，hooks 自动采集，profile YAML 注入。

## 理由
- 用户已深度使用 Claude Code，不需要额外学习曲线
- Solo Run 覆盖 80%+ 场景，Multi-agent 是低频需求
- 调试 trace 比调试 agent 通信简单一个数量级

## 后果
- (+) 系统简单，一个人能维护
- (+) trace 数据质量高（直接从 Claude Code 采集）
- (-) 无法做真正的并行 multi-agent 任务
- (-) 依赖 Claude Code 的 hooks 能力边界
```

## 蒸馏流程

### 触发时机

| 触发 | 做什么 | 输出到 |
|------|--------|--------|
| 每天凌晨 (nightly) | 蒸馏当天 trace → 更新 agents/ + projects/ | knowledge/ |
| 每周日 (weekly) | 汇总 7 天 → 更新 patterns/ + 发现新模式 | knowledge/ + 飞书 |
| 人工触发 ("回顾") | 深度分析 → 生成 decisions/ + patterns/ | knowledge/ + Claude Memory |

### 蒸馏脚本

```
evolution/distill_knowledge.py
  --scope daily|weekly|full
  --date 2026-04-02
  --apply  (实际写入 knowledge/)
```

### 与 Claude Memory 的关系

Claude Memory (Layer 3) 作为**索引和快照**:
- `project_agent_workforce.md` 引用 `→ 详见 ~/agent-workforce/knowledge/projects/`
- `feedback_*.md` 保持短小（行为反馈），长知识指向 knowledge/
- MEMORY.md 中新增一条: `## 长期记忆库: ~/agent-workforce/knowledge/`

Knowledge Base (Layer 2) 是**详细内容**:
- 文件体积不限
- 可以被项目的 CLAUDE.md 直接 include
- 可以被 nightly_eval.py 引用做回归测试

## 检索策略

AI 在新对话中的检索流程:
1. Claude Memory MEMORY.md 自动加载 (快照级上下文)
2. 进入特定项目 → 项目 CLAUDE.md 引用对应 knowledge/ 文件
3. 遇到未知问题 → 搜索 knowledge/patterns/ 找相似模式
4. 需要决策依据 → 查 knowledge/decisions/

## 存储策略

- agents/, projects/: YAML (结构化，脚本可更新)
- patterns/: YAML (结构化 + 描述)
- decisions/: Markdown (人类可读，ADR 格式)
- 所有文件 git 版本控制，变更可追溯

## 容量估算

按当前速率 (日均 71 条 trace):
- traces/: ~1MB/周，每月归档压缩
- knowledge/: ~50KB 总量，缓慢增长
- Claude Memory: 保持 <200KB（索引层）

## 实施步骤

1. 创建 knowledge/ 子目录结构
2. 写 distill_knowledge.py (从 trace 蒸馏到 knowledge/)
3. 首次全量蒸馏 (537+ traces → knowledge/)
4. Claude Memory 增加 knowledge/ 引用
5. nightly_eval.py 集成蒸馏步骤
6. 周报加入 knowledge 变更摘要
