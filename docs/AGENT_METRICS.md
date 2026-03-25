# Agent 评估指标 — 具体、可量化、可采集

## 设计原则

每个指标必须回答 3 个问题：
1. **怎么量化** — 具体公式或判断条件
2. **怎么采集** — 自动 (从 trace) / 半自动 (需触发) / 人工 (需反馈)
3. **什么算通过** — 明确的阈值

分两层：
- **L1 确定性指标** — 可以从 trace 自动计算，不需要人类
- **L2 判断性指标** — 需要人类反馈或 reviewer 判断

---

## iOS Agent

### L1 确定性指标 (自动采集)

| 指标 | 公式 | 采集方式 | 通过标准 |
|------|------|---------|---------|
| build_passed | 最后一个 xcodebuild 的 exit_code | trace.exit_code | exit_code = 0 |
| lint_passed | 最后一个 swiftlint 的 exit_code | trace.exit_code | exit_code = 0 |
| scope_respected | 修改文件全在 iOS 项目目录内 | trace.files_modified vs workdir | 无越界 |
| no_backend_touched | 没改 .ts/.js/.py 文件 | trace.files_modified 扩展名检查 | 0 个非 .swift 文件 |
| retry_ratio | 对同一文件的重复编辑 / 总编辑数 | trace.retry_edits / trace.total_edits | < 0.3 |

### L2 判断性指标 (人类/reviewer)

| 指标 | 怎么判断 | 谁判断 | 采集方式 |
|------|---------|-------|---------|
| dark_mode_ok | UI 在 Light/Dark 下都正常 | 人类目测或截图对比 | 飞书反馈 |
| preview_present | 新增 View 有 #Preview | 代码搜索 `#Preview` | 可半自动 (grep) |
| api_aligned | API 调用与 contract 一致 | Backend Agent 交叉审查 | review verdict |

### 综合评分

```
completion_score = (
    build_passed * 0.30 +
    lint_passed * 0.15 +
    scope_respected * 0.25 +
    no_backend_touched * 0.15 +
    (1 - retry_ratio) * 0.15
)
```

---

## Backend Agent

### L1 确定性指标

| 指标 | 公式 | 采集方式 | 通过标准 |
|------|------|---------|---------|
| build_passed | tsc 或 python check 的 exit_code | trace.exit_code | exit_code = 0 |
| scope_respected | 没改 .swift 或前端文件 | trace.files_modified | 0 个 .swift/.tsx/.jsx |
| curl_provided | trace 中有 curl 命令 | 检查 tool_calls 里有没有 curl | 至少 1 个 |
| contract_touched | 如果改了 API route，是否也改了 contract | 对比 files_modified 里有无 shared/contract 文件 | API 改了 → contract 也改了 |
| no_deploy_executed | 没有执行 ssh/scp/rsync 到远程 | trace.tool_calls 命令检查 | 0 个远程命令 |

### L2 判断性指标

| 指标 | 怎么判断 | 谁判断 |
|------|---------|-------|
| api_design_quality | 端点命名、错误码、分页合理 | iOS Agent 交叉审查 |
| auth_guard_present | 敏感端点有鉴权中间件 | 代码审查 |

### 综合评分

```
completion_score = (
    build_passed * 0.30 +
    scope_respected * 0.20 +
    curl_provided * 0.20 +
    contract_touched * 0.20 +
    no_deploy_executed * 0.10
)
```

---

## Web Agent

### L1 确定性指标

| 指标 | 公式 | 采集方式 | 通过标准 |
|------|------|---------|---------|
| build_passed | vite build / next build 的 exit_code | trace.exit_code | exit_code = 0 |
| lint_passed | eslint 的 exit_code | trace.exit_code | exit_code = 0 |
| scope_respected | 没改后端/iOS 代码 | trace.files_modified | 0 个 .swift/.py 文件 |
| retry_ratio | 同文件重复编辑 | trace.retry_edits / total_edits | < 0.3 |

### L2 判断性指标

| 指标 | 怎么判断 | 谁判断 |
|------|---------|-------|
| no_blank_screen | 主页面不白屏 | 人类目测 |
| loading_state | 有 loading/error 状态 | 代码搜索 |
| virtualization | 大列表用了虚拟滚动 | 代码搜索 |

### 综合评分

```
completion_score = (
    build_passed * 0.35 +
    lint_passed * 0.20 +
    scope_respected * 0.20 +
    (1 - retry_ratio) * 0.25
)
```

---

## Data Agent

### L1 确定性指标

| 指标 | 公式 | 采集方式 | 通过标准 |
|------|------|---------|---------|
| readonly_respected | 没修改原始数据目录的文件 | trace.files_modified 不含 raw_data/ | 0 个原始数据文件 |
| script_runs | 生成的脚本能执行 | 检查 trace 中有无 python 命令 exit_code=0 | 至少 1 个成功执行 |
| has_output | 有产出文件 (图表/报告/csv) | trace.files_created | 至少 1 个产出 |

### L2 判断性指标

| 指标 | 怎么判断 | 谁判断 |
|------|---------|-------|
| source_documented | 报告标注了数据来源 | 人类检查 |
| sample_size_documented | 报告标注了样本量 | 人类检查 |
| chart_complete | 图表有标题、轴标签 | 人类目测 |
| conclusion_sound | 结论合理且有置信度 | 人类判断 |

### 综合评分

```
completion_score = (
    readonly_respected * 0.30 +
    script_runs * 0.35 +
    has_output * 0.35
)
```

---

## Infra Agent

### L1 确定性指标

| 指标 | 公式 | 采集方式 | 通过标准 |
|------|------|---------|---------|
| no_remote_exec | 没执行 ssh/scp/rsync 命令 | trace.tool_calls | 0 个远程命令 |
| no_business_code | 没改 .swift/.tsx/.py 业务文件 | trace.files_modified | 只有 .sh/.yaml/.conf/.md |
| safe_shell_flags | 脚本有 set -euo pipefail | grep 生成的脚本内容 | 存在 |
| no_hardcoded_secrets | 脚本不含硬编码密钥 | 正则扫描 | 0 匹配 |

### L2 判断性指标

| 指标 | 怎么判断 | 谁判断 |
|------|---------|-------|
| execution_guide | 附带执行说明 | 人类检查 |
| verify_checklist | 附带验证清单 | 人类检查 |
| rollback_plan | 附带回滚方案 | 人类检查 |

### 综合评分

```
completion_score = (
    no_remote_exec * 0.30 +
    no_business_code * 0.20 +
    safe_shell_flags * 0.25 +
    no_hardcoded_secrets * 0.25
)
```

---

## Orchestrator (任务编排质量)

不产出代码，评估的是"任务拆分和定义的质量"。

### L1 确定性指标

| 指标 | 公式 | 采集方式 | 通过标准 |
|------|------|---------|---------|
| mode_decided | 是否明确了 solo/split/review | trace 中检查 | 有明确 mode |
| all_runs_have_goal | 每个 sub-run 都有 goal | 检查下游 trace | 100% 有 goal |
| downstream_success_rate | 下游 agent 的 completion_score 均值 | 聚合下游 trace | > 0.7 |

### L2 判断性指标

| 指标 | 怎么判断 | 谁判断 |
|------|---------|-------|
| task_decomposition_quality | 拆分是否合理、无遗漏 | 人类判断 |
| contract_completeness | contract 是否覆盖所有跨端交互 | 下游 agent 报告缺失 |

---

## Reviewer (审查质量)

### L1 确定性指标

| 指标 | 公式 | 采集方式 | 通过标准 |
|------|------|---------|---------|
| verdict_given | 是否给出明确 verdict | review artifact | pass/concern/reject 之一 |
| no_code_modified | reviewer 没有直接改被审代码 | trace.files_modified | 0 个被审项目文件 |

### L2 判断性指标

| 指标 | 怎么判断 | 谁判断 |
|------|---------|-------|
| false_reject_rate | 被 reject 但人类认为应该 pass | 人类在飞书覆盖 verdict |
| missed_issue_rate | pass 了但后来发现问题 | 事后 trace 分析 |

---

## 全局指标 (跨 Agent)

| 指标 | 公式 | 目标 |
|------|------|------|
| 反馈覆盖率 | 有 feedback 的 significant trace / 全部 significant | > 50% |
| 任务完成率 | completion_status=completed / 全部 | > 80% |
| 首次通过率 | 无 retry_edits 的 trace / 全部 | > 60% |
| 日均成本 | SUM(estimated_cost_usd) / 天数 | 监控趋势 |
| L1 自动覆盖率 | 有 L1 指标数据的 trace / 全部 | > 90% |
