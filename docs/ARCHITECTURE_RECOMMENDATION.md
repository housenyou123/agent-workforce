# Agent Workforce 架构建议（Claude-Native 版本）

## 文档目的

这份文档用于整理对 Agent Workforce 后续架构演进的建议，重点回答一个问题：

**这套系统怎么设计，才能在真实工作流里高效、稳定、低摩擦地长期运转起来。**

这里的建议基于当前项目现状，尤其参考了以下已有实现与约束：

- `Claude Code hooks` 已经接入
- `trace -> server -> feedback -> nightly eval` 闭环已经初步跑通
- 用户明确要求：安全边界强、人类确认明确、低摩擦反馈、先调研后决策
- 项目目标不是做通用框架，而是服务独立开发者的多项目 AI 协作系统

---

## 一句话结论

建议把 Agent Workforce 定义为：

**一个以 Claude Code session 为最小执行单元、以 trace 为核心资产、以规则为运行边界、以人工审批为安全阀的轻量协作操作系统。**

它不应该优先演化成“自治 agent swarm”，而应该优先成为：

1. 稳定的任务编排系统
2. 可靠的运行记录系统
3. 可审计的反馈学习系统

---

## 当前问题判断

现在最大的风险不是“做不出来”，而是**后面不容易高效运转**。

根因主要有 4 个：

### 1. 多 Agent 容易被高估

当前文档中的编队设计已经很完整，但从实际代码看，成熟度最高的部分是：

- hooks
- trace
- feedback
- nightly report

也就是说，系统当前更像是 **Claude 工作流增强层**，而不是成熟的多 Agent 运行时。

如果太早把重心放在“多 Agent 自动协作”，很容易让系统复杂度先失控。

### 2. 学习信号还不够干净

虽然已经有 `auto_score`、`failure pattern`、`nightly evaluator`，但很多关键信号仍然偏推断：

- goal 依赖 hook 捕获
- project / agent 依赖目录推断
- build / test / lint 成功还没有完全稳定结构化
- 工具调用摘要还比较粗

这意味着现在可以做分析，但还不适合过度自动进化。

### 3. 任务入口还不够标准化

虽然已有 `Task Envelope`，但“真正可执行”的 `Run Spec` 还不够清晰。

如果每次任务在执行前没有被标准化成：

- 改哪里
- 交什么
- 怎么验证
- 是否需要 review

那么后续再多 trace，也很难形成高质量学习。

### 4. Review 和进化流程还偏理想化

如果系统后面变成：

- 每个任务都重 review
- 每晚都尝试智能改 profile
- 每类问题都升级成多 Agent 协作

那么使用成本会很快上升，最后系统会“理论上很强，实际很重”。

---

## 设计原则

### 原则 1：贴着 Claude Code 原生能力生长

不要另起一个独立多 Agent runtime。

系统应建立在 Claude Code 已有能力之上：

- session
- workdir
- tools
- hooks
- human-in-the-loop

也就是说，Agent Workforce 的职责不是替代 Claude Code，而是在它之上增加：

- 控制面
- 审计面
- 学习面

### 原则 2：以任务流水线为核心，不以 Agent 网络为核心

不要把“agent 数量”作为系统能力的主要来源。

真正重要的是任务如何被：

1. 定义
2. 约束
3. 执行
4. 验证
5. 记录
6. 学习

系统应该是“任务流水线”，而不是“agent 群聊”。

### 原则 3：默认单 Agent，按需多 Agent

多 Agent 应该是例外模式，而不是默认模式。

建议只保留 3 种执行模式：

#### Solo Run

默认模式，覆盖绝大多数任务。

特点：

- 一个 agent
- 一个 workdir
- 一次 Claude session
- 明确验证方式

#### Split Run

只用于明确的跨端任务，例如：

- iOS + Backend
- Web + Backend
- Data + Web

前提：

- 必须先定义 contract
- 必须拆成两个以上可独立验证的 run

#### Review Run

reviewer 独立运行，只做审查，不写业务代码。

### 原则 4：先做确定性验证，再做智能评测

系统评估要分两层：

#### 第一层：确定性验证

- build 是否通过
- test 是否通过
- lint 是否通过
- 是否越过文件边界
- 是否满足 deliverables
- 是否满足 contract

#### 第二层：智能评测

- follow-up 次数
- 人类 post-edit ratio
- reviewer concern / reject
- frustration signal
- 夜间 failure pattern 分析

顺序不能反。

如果第一层不稳定，第二层再聪明也容易把噪音当信号。

### 原则 5：进化要保守，提案优先于自动改动

夜间评测系统更适合做：

- insight
- proposal
- regression result

而不是直接自动修改 profile 本体。

短期内建议：

- 自动积累知识
- 半自动生成改进提案
- 谨慎处理 profile 升级

---

## 建议中的目标架构

建议拆成 5 层。

### 1. Session Layer

最小执行单元就是一次 Claude session。

每个 session 都应该是一个受约束的 run：

- 有明确输入
- 有明确 workdir
- 有明确边界
- 有明确输出
- 有明确验证方式

这里不要做常驻 agent，不要做 agent 之间的隐式通信。

### 2. Control Layer

这层不是“智能聊天调度器”，而是**任务编译器**。

职责：

1. 理解用户目标
2. 判断走 solo / split / review 哪种模式
3. 生成 Task
4. 生成每个 worker 的 Run Spec
5. 挂上 contract、rules、approval gate

换句话说，这层主要负责 **定义边界**，而不是 **过程驱动**。

### 3. Artifact Layer

worker 之间不能直接通信，只能通过受控对象协作。

建议保留并强化以下对象：

- `Task Envelope`
- `Artifact Registry`
- `Contract`
- `Review Artifact`
- `Discovery Artifact`

核心原则：

- 信封是全局上下文
- run 只消费摘要和引用，不直接互相传话
- 最终协作对象是 artifact，不是消息

### 4. Event / Trace Layer

建议把 trace 从“session 摘要”升级成“事件流 + 摘要”双层模型。

#### Event

按事件记录：

- `run_started`
- `goal_captured`
- `tool_called`
- `verification_finished`
- `review_finished`
- `feedback_received`
- `approval_requested`
- `approval_resolved`

#### Summary

再离线汇总成：

- 单次 run trace
- daily stats
- agent report
- failure pattern input

这样更适合后续：

- 回放
- 调试
- 找瓶颈
- 统计误判
- 做高质量 nightly analysis

### 5. Learning Layer

夜间评测建议分三种输出：

#### Insight

例如：

- 哪类任务 follow-up 最多
- 哪类任务经常 build fail
- 哪类路由经常错误

#### Proposal

例如：

- 某类任务需要更强 verification checklist
- 某类任务默认走 split run
- 某类任务必须先读哪些文件

#### Regression Result

用于判断某个提案是否值得升级为正式规则或 profile 变更。

---

## 核心数据对象建议

### 1. Task

表示一个人类目标。

建议字段：

- `task_id`
- `human_goal`
- `interpreted_goal`
- `mode` (`solo` / `split` / `reviewed_split`)
- `risk_level`
- `contracts`
- `status`

### 2. Run Spec

这是建议新增的最关键对象。

它比当前 `Task Envelope` 更贴近真实执行。

建议字段：

- `run_id`
- `task_id`
- `agent_id`
- `workdir`
- `allowed_paths`
- `input_artifacts`
- `contract_refs`
- `expected_outputs`
- `verification_steps`
- `needs_review`
- `needs_human_approval`

一句话：**Run Spec 就是一次 Claude session 的执行说明书。**

### 3. Artifact

保留当前方向，建议标准化成：

- `final`
- `review`
- `discovery`
- `verification`

### 4. Approval Record

建议新增审批对象，用于统一管理：

- 部署确认
- 规则修改
- 新增 Agent
- 架构升级
- 高风险操作

建议状态：

- `pending`
- `approved`
- `rejected`
- `needs_discussion`
- `resumed`
- `aborted`

---

## 真正提升可行性的 7 个具体动作

### 1. 把系统定位收紧

短期不要把目标定义成“多 Agent 自治平台”。

更适合的定义是：

**Claude session orchestration + trace intelligence**

这样更符合当前实现成熟度，也更容易持续推进。

### 2. 把执行模式缩成 3 种

只保留：

- `Solo Run`
- `Split Run`
- `Review Run`

不要把所有任务都多 Agent 化。

### 3. 引入 Run Spec

这是最关键的结构化升级。

没有 Run Spec，自动路由、review、评估、学习都不容易做稳。

### 4. 先补确定性验证层

优先让系统可靠判断：

- 做没做成
- 是否越界
- 是否满足 contract
- 是否具备可验证输出

这层比“更聪明的 nightly eval”更重要。

### 5. 先优化 checklist / routing / playbook，再改 profile prompt

建议把进化优先级设成：

1. knowledge accumulation
2. routing rules
3. verification templates
4. review checklists
5. profile prompt changes

原因：

- 前四者风险低、收益稳
- 直接动 prompt 本体风险更高

### 6. 把 trace 升级成事件流

当前 summary 型 trace 已经有价值，但如果希望后续真正优化运营效率，需要事件层支撑。

事件层会让下面这些问题更容易回答：

- 哪类任务最常卡在验证
- 哪类任务最常卡在 review
- 哪类任务需要人类频繁补充说明
- 哪类审批最拖慢系统效率

### 7. 设置 WIP 限制和升级节奏

为了让系统长期稳定，建议加几个运营约束：

- 同一项目同一时间默认只允许 1 个 active run
- 多 Agent 任务默认最多 2 个 worker + 1 reviewer
- nightly evaluator 默认只出提案，不直接自动改 profile
- prompt/profile 升级按周批量处理，不按天自动改
- 架构级演进按月 review

---

## 建议的 v1 / v2 边界

### v1 必做

这些能力是“系统能高效运转”的基础。

1. hooks 稳定采集
2. JSONL + SQLite 双写稳定
3. Run Spec 引入
4. deterministic verification
5. feedback / approval 状态机
6. nightly evaluator 降级为 insight + proposal 引擎
7. solo / split / review 三种执行模式正式化

### v2 再做

这些能力有价值，但不应该抢在 v1 前面。

1. 更复杂的 cross-review 自动修复链
2. profile 自动升级
3. 更多 agent 类型拆分
4. 更复杂的多阶段 orchestration
5. 高自由度 agent 协作网络

---

## 两周内最划算的推进顺序

### 第 1 周

目标：把“运行”做稳。

建议优先级：

1. 明确 Solo / Split / Review 三种模式
2. 设计并落地 `Run Spec`
3. 补齐 verification schema
4. 让服务端支持 approval records

### 第 2 周

目标：把“学习”做稳。

建议优先级：

1. trace 事件层设计
2. nightly evaluator 改成 proposal-first
3. 路由规则和 checklist 沉淀
4. 只对少数高频任务类型做优化闭环

---

## 最终建议

如果这个系统想长期高效运转，关键不在于：

- agent 更多
- prompt 更复杂
- 调度更聪明

关键在于 4 件事：

1. 任务足够标准
2. 验证足够确定
3. 反馈足够低摩擦
4. 进化足够保守

所以最推荐的方向是：

**先把 Agent Workforce 做成一个稳定的 Claude-native 任务操作系统，再逐步叠加多 Agent 协作能力。**

这样系统会更容易真正跑起来，也更容易在 24 个项目的真实工作流里持续演进。
