# Agent Workforce 如何借鉴 autoresearch

## 文档目的

这份文档用于回答：

**Karpathy 的 `autoresearch` 项目里，有哪些设计适合借到 Agent Workforce 里，哪些不适合直接照搬。**

参考仓库：

- [karpathy/autoresearch](https://github.com/karpathy/autoresearch)

---

## 一句话结论

`autoresearch` 很值得借鉴，但**适合借“运行哲学”和“实验机制”，不适合直接当 Agent Workforce 的主框架。**

原因很简单：

- `autoresearch` 解决的是 **单问题、单代码面、单数值指标优化**
- `Agent Workforce` 解决的是 **多项目、多技术栈、多目标任务协作**

所以最合理的策略不是“接入 autoresearch 框架”，而是：

**把 autoresearch 的受控实验思想，局部吸收到 Agent Workforce 的 run / review / evolution 机制里。**

---

## `autoresearch` 的核心设计

根据仓库 README，可以把它的核心设计概括成 5 点：

### 1. 极小改动面

它故意把系统压缩到极少的关键文件：

- `prepare.py`：固定，不改
- `train.py`：agent 唯一主要修改目标
- `program.md`：由人类编写，用来指导 agent

这意味着 agent 的探索空间被强约束，diff 容易 review，失败容易回滚。

### 2. 固定实验预算

每次实验固定跑 5 分钟训练。

这个设计的关键价值不是省时间，而是：

- 让实验结果可比较
- 让 agent 在有限 budget 下优化
- 让 keep/discard 判断更直接

### 3. 单一评测指标

它用一个主指标：

- `val_bpb`，越低越好

因为目标是单数值优化，所以 agent 可以稳定进入“提出改动 -> 运行实验 -> 判断是否更优”的闭环。

### 4. `program.md` 驱动 agent

在这个项目里，人类主要不是直接改 Python，而是改 `program.md`，也就是改：

- agent 的工作原则
- 实验方式
- 决策规则

这本质上是一个超轻量的“运行程序”。

### 5. 保守的 keep/discard 机制

核心问题不是“这次改动是否很聪明”，而是：

**这次实验结果是否比当前 baseline 更好。**

它天然适合：

- 快速试错
- 简单决策
- 自动循环

---

## 为什么它不能直接成为 Agent Workforce 主框架

虽然很有启发，但它和 Agent Workforce 的问题空间差异非常大。

### 1. 你的系统不是单指标优化

`autoresearch` 有明确单一指标：

- `val_bpb`

而 Agent Workforce 里的任务很多都不是单指标：

- iOS 页面是否“完成”不能只靠一个数字
- 后端接口是否“完成”需要 contract + build + curl + review
- 数据分析是否“完成”需要来源、样本量、图表、可复现性

所以你不能直接把它的自治循环套到整个平台。

### 2. 你的系统是多项目、多技术栈、多目标

`autoresearch` 的研究对象几乎只有一个：

- 单 GPU 上的小模型训练改进

而你的系统面对的是：

- iOS
- Backend
- Web
- Data
- Infra
- Review
- Orchestration

这意味着统一的自动优化循环必须更保守、更分层。

### 3. 你的系统有更强的安全边界

`autoresearch` 的默认前提是：

- agent 自主改代码
- agent 自主跑实验
- 结果差就丢弃

而你的系统里很多事情是不能“先做再回退”的：

- 规则修改
- 架构演进
- 生产相关配置
- 部署动作
- 高风险跨项目改动

所以你这里不能把所有任务都当作“可自由试验”。

---

## 最值得借的 6 个设计

---

## 1. 借 `program.md` 的思路，落成 `Run Spec / Done Spec`

### autoresearch 的启发

它把 agent 的核心运行逻辑浓缩进 `program.md`。

这说明一个事实：

**agent 不一定需要复杂 runtime，很多时候更需要一份清晰、可执行、可迭代的任务程序。**

### 在 Agent Workforce 里怎么落

把这个思路转成：

- `Run Spec`
- `Done Spec`

也就是说，每个 sub-agent run 在开始前，不只是拿到一句自然语言任务，而是拿到：

- 目标
- 改动范围
- 交付物
- 验证方式
- keep/discard 规则

### 建议

把 `program.md` 的思想落为：

- 对人类：`Task Envelope`
- 对 sub-agent：`Run Spec`
- 对评估：`Done Spec`

---

## 2. 借“极小改动面”，落成 `bounded scope run`

### autoresearch 的启发

它几乎只让 agent 改一个主文件：

- `train.py`

这极大降低了：

- review 成本
- 回滚成本
- 漂移风险

### 在 Agent Workforce 里怎么落

给每个 run 加：

- `workdir`
- `allowed_paths`
- `forbidden_paths`

让每个 sub-agent 只改一个非常小的范围。

例如：

- iOS run 只改 `StoryDetailView` 相关目录
- Backend run 只改一个 endpoint 和对应 contract
- Web run 只改一个页面和配套组件

### 建议

把“一个任务一个大范围 agent”改成：

**一个 run 一个小边界。**

---

## 3. 借“固定实验预算”，落成固定验证预算

### autoresearch 的启发

它不是无限跑训练，而是固定 5 分钟。

关键价值是：

- 结果可比
- 决策简单
- agent 不会无限拖长实验

### 在 Agent Workforce 里怎么落

不是固定“5 分钟”，而是固定“验证组合”。

例如：

- iOS：`xcodebuild + swiftlint + manual checklist`
- Backend：`tsc/python check + curl`
- Web：`build + eslint + manual smoke`
- Data：`报告完整性 + 复现命令 + 来源/样本量检查`
- Infra：`脚本静态检查 + 执行说明 + approval gate`

### 建议

每类 run 都有自己的标准验证预算，不允许 agent 自己发明完成标准。

---

## 4. 借“单一 keep/discard 机制”，落成低维 run 决策

### autoresearch 的启发

它的核心判断非常低维：

- keep
- discard

### 在 Agent Workforce 里怎么落

对每个 run，先不要一开始就搞复杂评分体系。

先收敛成：

- `advance`
- `discard`
- `blocked`
- `needs_review`

其中：

- `advance`：满足 Done Spec，可进入下游或合并
- `discard`：没有满足关键验证，改动不应进入主链
- `blocked`：缺上下文、缺 contract、缺 approval
- `needs_review`：确定性验证过了，但仍需 reviewer 判断

### 建议

先做低维状态，再叠加质量分。

不要让系统一开始就依赖复杂综合分数驱动流程。

---

## 5. 借“分支实验”思路，落成 worktree / branch sandbox

### autoresearch 的启发

它本质上是把一次次实验与当前 baseline 分开。

### 在 Agent Workforce 里怎么落

对于高风险 run 或多 agent run，建议：

- 每个 run 进入独立 worktree 或 branch
- review pass 后再回主任务线
- reject / discard 时直接丢弃该 run 工作副本

### 建议

这个模式特别适合：

- 后端 contract 改动
- 多 agent 并行开发
- 高风险 infra 变更
- 探索型重构

---

## 6. 借“实验记录表”，落成 `run result ledger`

### autoresearch 的启发

它的实验记录很结构化，便于比较、筛选和分析。

### 在 Agent Workforce 里怎么落

在 trace 之外，单独维护一个更轻的结果账本。

例如每次 run 记录：

- `run_id`
- `agent_id`
- `task_type`
- `completion_status`
- `quality_score`
- `review_verdict`
- `duration_sec`
- `files_modified_count`
- `verification_passed`

这层比完整 trace 更适合：

- dashboard
- agent 对比
- 失败模式统计
- nightly evaluator 快速读取

### 建议

完整 trace 负责审计，
ledger 负责运营和分析。

---

## 不建议直接借的 4 个地方

### 1. 不要直接照搬“完全自治循环”

原因：

- 你的任务很多不是单指标
- 你的系统有人类确认边界
- 你的系统跨项目、跨技术栈，错误成本更高

### 2. 不要直接照搬“单文件修改模型”

这个模式适合 `autoresearch`，但不适合你的大多数业务项目。

不过可以借它的思想：

- 每次 run 限小范围，不等于只能改一个文件

### 3. 不要把所有 evolution 都做成 overnight auto-search

更适合被 autoresearch 化的对象是：

- routing rules
- review checklist
- prompt phrasing
- verification templates

不适合直接 autoresearch 化的对象是：

- 生产逻辑
- 规则体系
- agent 架构本体

### 4. 不要把所有任务都转成数值优化问题

你的系统里有很多高价值任务无法压缩成一个数字。

比如：

- 页面体验
- 架构拆分质量
- 接口设计合理性
- 数据分析结论可信度

所以要接受：

- 有些任务适合数值评估
- 有些任务适合 checklist
- 有些任务适合 review verdict

---

## 在 Agent Workforce 里最适合“借 autoresearch 思维”的地方

最适合的是“局部自治优化回路”，而不是整个平台。

### 场景 1：Routing Rule 优化

目标：

- 找出哪些任务经常被错误路由
- 调整路由规则
- 看是否减少 follow-up / reject / rework

这很适合做小范围 keep/discard 实验。

### 场景 2：Review Checklist 优化

目标：

- 哪些 checklist 项最能提前发现问题
- 哪些 checklist 太啰嗦、没价值

这也适合做保守迭代。

### 场景 3：Done Spec / Verification Template 优化

目标：

- 哪类任务最常“做了但没验成”
- 哪类任务常因验收定义不清被阻塞

这特别适合做模板优化。

### 场景 4：Nightly Evaluator Prompt / Policy 优化

目标：

- 提高 failure pattern 提取质量
- 提高 proposal 的可执行性

这也是很好的实验对象。

---

## 推荐的吸收方式

最推荐的做法不是“集成 autoresearch”，而是新增一个内部概念：

### `Experiment Mode`

这个模式只对有限对象开放：

- routing rule
- review checklist
- verification template
- evaluator prompt

运行方式：

1. 选择一个可比较对象
2. 固定验证预算
3. 在小范围内修改
4. 跑回归或对照
5. 输出 `keep / discard / needs_human_review`

这样就把 autoresearch 的精华吸收进来了，同时不破坏主系统安全边界。

---

## 推荐的最终判断

如果问：

**这个项目我们可以用什么吗？**

最准确的回答是：

### 可以直接借的

- `program.md` 思路
- 小 scope 改动模式
- 固定评测预算
- keep/discard 决策
- 实验账本
- worktree / 分支实验思路

### 适合局部吸收的

- 自治优化循环
- overnight experimentation

### 不适合直接照搬的

- 整个平台完全自治
- 用单指标统一所有任务
- 把所有 agent 行为都变成实验搜索

---

## 最终结论

`autoresearch` 对 Agent Workforce 最有价值的启发不是“多 agent 自动研究”，而是：

**把 agent 的自主性建立在极小 scope、固定评测、结构化记录、保守保留/丢弃机制之上。**

这套思想非常适合吸收到 Agent Workforce 中，尤其适合：

- run 设计
- done spec 设计
- nightly evolution 设计
- 小范围自治优化回路

但它不适合作为 Agent Workforce 的主运行框架。

