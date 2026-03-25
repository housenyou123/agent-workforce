# Agent Workforce 完成定义与数据衡量规范

## 文档目的

这份文档回答两个问题：

1. 如何用数据衡量一个目标是否完成
2. 是否需要给每个 sub-agent 细化目标，以及应该细化到什么程度

结论先说：

**需要细化，但不是给每个 sub-agent 写宏大目标，而是给每次实际运行的 sub-agent 一份可验证的局部完成定义。**

也就是说，系统不应只记录“做了什么”，而应记录：

- 本次 run 的目标是什么
- 交付物是什么
- 如何验证
- 是否越界
- 质量如何

这份规范基于当前已有设计：

- [orchestrator](/Users/housen/agent-workforce/profiles/orchestrator/v1.0.yaml)
- [ios_agent](/Users/housen/agent-workforce/profiles/ios_agent/v1.0.yaml)
- [backend_agent](/Users/housen/agent-workforce/profiles/backend_agent/v1.0.yaml)
- [web_agent](/Users/housen/agent-workforce/profiles/web_agent/v1.0.yaml)
- [data_agent](/Users/housen/agent-workforce/profiles/data_agent/v1.0.yaml)
- [infra_agent](/Users/housen/agent-workforce/profiles/infra_agent/v1.0.yaml)
- [reviewer](/Users/housen/agent-workforce/profiles/reviewer/v1.0.yaml)

---

## 一、目标分层

建议把“完成”拆成 4 层。

### Layer 1：Task 完成

这是面向人类目标的一层，回答：

**用户想做的事情，整体做成了吗？**

判断字段：

- `all_required_runs_completed`
- `all_required_verifications_passed`
- `no_open_blockers`
- `no_pending_required_approvals`

状态建议：

- `completed`
- `partial`
- `blocked`
- `failed`

### Layer 2：Run 完成

这是最关键的一层，回答：

**某个 sub-agent 这一次 run，是否完成了自己的局部目标？**

判断字段：

- `deliverables_met`
- `verification_passed`
- `scope_respected`
- `contract_respected`
- `handoff_ready`

状态建议：

- `completed`
- `completed_with_concern`
- `blocked`
- `failed`

### Layer 3：Review 完成

回答：

**该 run 是否通过了必要的审查或验证？**

判断字段：

- `review_required`
- `review_verdict`
- `concern_count`
- `reject_count`

当前阶段 reviewer 还是 checklist 模式，因此这里可以先记录为：

- `deterministic_review_passed`
- `cross_review_passed`

### Layer 4：Quality 完成

回答：

**任务虽然做完了，但质量够不够好？**

这层不决定“完没完成”，而决定“完成得怎么样”。

判断字段：

- `build_success`
- `test_pass`
- `lint_clean`
- `human_feedback`
- `follow_up_count`
- `human_post_edit_ratio`
- `reverted`
- `auto_score`

---

## 二、必须新增的核心对象：Done Spec

建议在当前 `Task Envelope` 之下，为每一个实际运行的 sub-agent 补一个 `Done Spec`。

不是每个 agent 一份抽象目标，而是每次 run 一份可执行定义。

建议结构：

```json
{
  "run_id": "run_backend_001",
  "task_id": "task_20260325_001",
  "agent_id": "backend_agent",
  "goal": "实现分享接口并保持现有登录流程不受影响",
  "scope": {
    "workdir": "/path/to/backend",
    "allowed_paths": ["src/api", "src/shared/contracts"]
  },
  "deliverables": [
    "POST /api/share endpoint",
    "response schema",
    "curl verification example"
  ],
  "verification": [
    "tsc passes",
    "curl returns 200 and expected fields"
  ],
  "constraints": [
    "do not modify iOS code",
    "update contract if API changes"
  ],
  "handoff": {
    "to": "ios_agent",
    "summary_required": true
  },
  "completion_rule": "all_deliverables_met && all_verification_passed && scope_respected"
}
```

一句话：

**Done Spec 是 run 的 Definition of Done + Evidence Plan。**

---

## 三、统一数据模型

建议每个 run 都写回一份结构化结果。

```json
{
  "run_id": "run_backend_001",
  "agent_id": "backend_agent",
  "status": "completed",
  "deliverables_met": true,
  "verification_passed": true,
  "scope_respected": true,
  "contract_respected": true,
  "review_verdict": "pass",
  "quality_score": 0.86,
  "evidence": {
    "commands": [
      "npm run build",
      "curl -X POST ..."
    ],
    "artifacts": [
      "shared/contracts/share.ts"
    ],
    "files_modified": [
      "src/routes/share.ts"
    ]
  }
}
```

---

## 四、统一评分框架

建议把 run 的结果分成两部分：

### 1. Completion Score

是否完成。

建议权重：

- `deliverables_met`: 35%
- `verification_passed`: 35%
- `scope_respected`: 15%
- `contract_respected`: 10%
- `handoff_ready`: 5%

只要 `verification_passed = false`，Completion Score 最高不超过 `0.59`。

只要 `scope_respected = false`，直接标记为 `failed` 或 `reject`。

### 2. Quality Score

完成质量。

建议权重：

- `deterministic_checks`: 40%
- `review_result`: 20%
- `human_feedback`: 20%
- `implicit_signals`: 20%

其中：

- deterministic_checks：build / test / lint / schema / reproducibility
- review_result：pass / concern / reject
- human_feedback：👍 / 🔄 / 👎 / ⭐
- implicit_signals：follow-up、post-edit、revert、frustration

---

## 五、各 Agent 的完成定义细化

这里不是给每个 agent 写“大愿景”，而是定义：

- 它每次 run 的 Done Spec 长什么样
- 它最重要的交付物是什么
- 什么数据能证明它做完了

---

## 六、Orchestrator 的完成定义

注意：

orchestrator 不是业务代码产出者，它的完成不看 build/test，而看“任务编译质量”。

### 目标

把人类目标转成可执行任务。

### 必需交付物

- `task interpretation`
- `mode decision`：solo / split / review
- `run specs`
- `contracts`（如有）
- `verification plan`
- `approval gates`（如有）

### 完成条件

- 任务拆分完整
- 没有遗漏必须的 run
- 多 agent 任务包含 contract
- 每个 run 都有 verification
- 高风险任务挂上 approval

### 核心证据

- 是否生成完整 Run Spec
- 是否生成 Contract
- 是否补齐 review / approval 标记
- 下游 run 是否因为 spec 缺失被 blocker

### 数据指标

- `routing_accuracy`
- `spec_completeness_rate`
- `missing_verification_rate`
- `wrong_mode_rate`
- `downstream_blocked_by_spec_count`

### 判定规则

- `completed`: 所有必要 run spec 生成完备
- `completed_with_concern`: spec 可运行，但缺少部分验证或 review 标记
- `failed`: 路由错误、漏拆子任务、漏 contract、漏高风险审批

---

## 七、iOS Agent 的完成定义

参考当前 profile 中的质量门槛：

- `xcodebuild build 编译通过`
- `无 SwiftLint error`
- `支持 Dark Mode`

### 目标类型

- View / ViewModel 实现
- 本地存储接入
- 系统框架集成
- 基于已有 contract 的 API 对接

### 必需交付物

- 对应 Swift 文件修改
- 如有 UI：必要预览或说明
- 如有 API 对接：请求与 contract 对齐
- 验证命令或人工验证说明

### 完成条件

- 目标页面 / 功能已实现
- `xcodebuild build` 成功
- 无 SwiftLint error
- 未越界修改后端 / web / contract

### 核心证据

- `xcodebuild` 结果
- `swiftlint` 结果
- 修改文件列表
- 如有 API：请求模型与 contract 对齐

### 建议数据字段

- `ios_build_success`
- `swiftlint_clean`
- `dark_mode_checked`
- `preview_present`
- `api_contract_aligned`

### 特殊失败定义

以下任一项出现，run 不能算完成：

- build fail
- 越界定义 API
- 修改后端 / web 代码
- 无法说明如何验证

---

## 八、Backend Agent 的完成定义

参考当前 profile 中的质量门槛：

- `tsc 编译无错误`
- `Python 语法检查通过`
- `API 变更必须更新 contract 文件`
- `新增端点附带 curl 测试命令`

### 目标类型

- REST API 实现
- 数据库 schema 变更
- AI pipeline 编排
- shared/ contract 维护

### 必需交付物

- 代码变更
- contract 更新或声明“无 contract 变化”
- curl 示例
- 验证结果

### 完成条件

- TypeScript 或 Python 验证通过
- 如 API 变更，contract 已更新
- 如新增 endpoint，有 curl 证明
- 未修改 iOS / Web 代码
- 未涉及部署执行

### 核心证据

- `tsc` 或 Python check 输出
- contract 文件差异
- curl 命令与响应摘要
- files modified

### 建议数据字段

- `backend_build_success`
- `python_syntax_ok`
- `contract_updated`
- `curl_provided`
- `auth_guard_present`

### 特殊失败定义

- API 改了但 contract 没改
- 新 endpoint 无 curl
- 越界改 iOS / Web
- 执行了部署动作

---

## 九、Web Agent 的完成定义

参考当前 profile 中的质量门槛：

- `vite build / next build 无错误`
- `eslint 无 error`
- `主流程页面无白屏`

### 目标类型

- 页面开发
- 组件开发
- API 对接
- Dashboard / 数据可视化

### 必需交付物

- 页面或组件代码
- API 使用与 contract 对齐
- build 结果
- lint 结果
- 如有关键流程：人工验证说明

### 完成条件

- build 成功
- eslint 无 error
- 主流程无白屏
- 未越界改后端 / iOS / DB

### 核心证据

- `vite build` / `next build`
- `eslint`
- 关键页面列表
- API contract 对齐记录

### 建议数据字段

- `web_build_success`
- `eslint_clean`
- `no_blank_screen_verified`
- `loading_state_present`
- `error_state_present`
- `virtualization_used_if_large_list`

### 特殊失败定义

- build fail
- ESLint error
- 页面白屏
- API 调用与 contract 不一致

---

## 十、Data Agent 的完成定义

参考当前 profile 中的质量门槛：

- 结论标注数据来源和样本量
- 图表有标题、轴标签、数据来源
- 统计结论标注置信度或 p-value
- 脚本可复现

### 目标类型

- 数据分析
- 数据质量检查
- 可视化
- 脚本生成

### 必需交付物

- 分析报告、图表或脚本
- 数据来源说明
- 样本量说明
- 置信度 / p-value（如适用）
- 复现说明

### 完成条件

- 输出格式符合任务要求
- 不修改原始数据
- 报告中包含来源、样本量、置信度
- 脚本可运行、路径不硬编码

### 核心证据

- 报告文件
- 图表文件
- 样本统计
- 复现命令
- 只读数据访问记录

### 建议数据字段

- `source_documented`
- `sample_size_documented`
- `confidence_documented`
- `chart_metadata_complete`
- `reproducible_script`
- `readonly_respected`

### 特殊失败定义

- 修改了原始数据
- 结论无来源或样本量
- 图表无标签
- 分析不可复现

---

## 十一、Infra Agent 的完成定义

参考当前 profile 中的质量门槛：

- `脚本有 set -euo pipefail`
- `Dockerfile 有 .dockerignore`
- `敏感信息使用环境变量`
- `产出附带执行说明`

### 目标类型

- 本地构建脚本
- Docker / CI 配置
- 环境问题排查
- 部署脚本编写

### 必需交付物

- 脚本 / 配置文件
- 执行说明
- 风险提醒
- 如有部署相关：明确“仅供人类执行”

### 完成条件

- 产出脚本或配置可读可执行
- 附带执行说明
- 无硬编码敏感信息
- 不执行远程操作
- 不直接改业务逻辑

### 核心证据

- 脚本内容
- README / 注释
- dry-run 或说明
- 未触发远程操作记录

### 建议数据字段

- `has_safe_shell_flags`
- `has_dockerignore`
- `uses_env_vars`
- `execution_guide_present`
- `dry_run_supported`
- `human_approval_required_marked`

### 特殊失败定义

- 直接部署
- 远程 SSH / 远程 DB 操作
- 修改业务代码
- 配置中泄露敏感信息

---

## 十二、Reviewer 的完成定义

当前 reviewer 不是独立 agent 运行时，而是 checklist / 交叉 review 机制。

所以当前阶段 reviewer 的完成定义不应该是“写出完美评论”，而是：

**是否完成了受控审查，并给出结构化 verdict。**

### 必需交付物

- `verdict`
- `issues`
- `suggestions`
- `checklist results`

### 完成条件

- verdict 明确
- 审查维度与目标 agent 匹配
- 检查了 quality_gates
- 没有越权直接改代码

### 核心证据

- review artifact
- checklist 打勾结果
- concern / reject 原因

### 建议数据字段

- `review_dimensions_checked`
- `quality_gates_checked`
- `verdict`
- `issues_count`
- `false_reject_rate`

### 特殊失败定义

- 没给明确 verdict
- 审查维度不匹配
- reviewer 自己改了被审代码

---

## 十三、是否要给每个 sub-agent 都细化目标

结论：

**要，但要细化到 run，不要细化到抽象 agent 身份。**

也就是说，推荐方式不是：

- “ios_agent 的长期目标是什么”
- “backend_agent 的宏观使命是什么”

而是：

- “这一次 ios_agent run 的 Done Spec 是什么”
- “这一次 backend_agent run 的 Evidence 是什么”

因此建议遵循：

### 需要强 Done Spec 的

- ios_agent
- backend_agent
- web_agent
- data_agent
- infra_agent

### 需要轻 Done Spec 的

- reviewer

### 需要编排质量定义的

- orchestrator

---

## 十四、推荐的最小落地方案

如果只做最小可运行版本，建议先补这 5 个字段到每个 run：

- `goal`
- `deliverables`
- `verification`
- `constraints`
- `completion_status`

再加 5 个结果字段：

- `deliverables_met`
- `verification_passed`
- `scope_respected`
- `review_verdict`
- `quality_score`

这样已经足够支持：

- task 完成率统计
- 各 agent 完成率对比
- 哪类任务最常“做了但没验成”
- 哪类 agent 最常“做完但质量低”

---

## 十五、最终建议

Agent Workforce 后续如果想真正做到“数据驱动地衡量任务完成”，关键不是让每个 agent 写更多话，而是让每个 run 都带着一份结构化的完成定义进入系统。

一句话总结：

**目标要下沉到 run，完成要靠 evidence，质量要和完成分开统计。**

推荐执行顺序：

1. 先给每个执行型 sub-agent 引入 Done Spec
2. 再给 orchestrator 引入 run spec completeness 指标
3. reviewer 先保持 checklist 模式
4. 最后再把这些字段正式接入 trace / server / nightly evaluator

