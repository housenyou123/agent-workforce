# Handoff: Agent Workforce — Auto Rating 实现

## 快速恢复

> "读一下 ~/agent-workforce/handoffs/2026-03-27-auto-rating.md，继续 Agent Workforce"

## Session Metadata
- Created: 2026-03-27 12:41
- Continues from: `handoffs/2026-03-27-day2.md`
- Branch: main
- **未 commit，未 sync**

## Current State Summary

实现了 **auto_rate() 自动评分**，解决反馈覆盖率 0% 的瓶颈。每次会话结束时 trace_engine 自动算 1-4 分，写入 `auto_feedback` 字段，systemMessage 展示结果。用户可用 aw1-4 手动覆盖。

代码改完、测试 9/9 通过。**尚未 git commit，未 sync 到服务器。**

## Work Completed

- [x] `.zshrc` 的 `claude()` 加了 `_aw_post_claude`（用户手动）
- [x] `trace_schema.py`: 新增 `auto_feedback: Optional[int]` 字段
- [x] `trace_engine.py`: 新增 `auto_rate()` + 接入 `process_session()` + quality_score 兜底
- [x] `session_stop_trace.sh`: systemMessage 展示 `auto: 3/good`
- [x] `test_auto_rate.py`: 9 个测试，全部通过
- [x] 端到端测试通过

## auto_rate 逻辑

| 评分 | 条件 |
|------|------|
| 1 bad | build 失败 / 凭据泄露 / 越界 |
| 2 fine | retry_edits > 2 或 rounds > 5 |
| 4 golden | build 显式通过 + 0 retry + 有文件产出 |
| 3 good | 默认 (以上都不是) |

quality_score: human_feedback 优先，否则 auto_feedback 映射 {4:1.0, 3:0.8, 2:0.4, 1:0.0}

## Immediate Next Steps

1. **排查 `.hook_buffer.jsonl` 为空** — auto_trace.sh PostToolUse hook 可能没收到 stdin
2. `git commit` + `bash scripts/sync_to_server.sh`
3. 正常工作积累数据，观察 auto_feedback 分布
4. 50 条后对比 auto vs human 一致性

## Critical Files

| File | What Changed |
|------|-------------|
| `scripts/trace_engine.py` | +auto_rate() ~line 264, process_session 接入, quality_score 兜底 |
| `scripts/trace_schema.py` | +auto_feedback 字段 |
| `hooks/session_stop_trace.sh` | systemMessage 展示 auto rating |
| `scripts/test_auto_rate.py` | 新文件, 9 tests |
| `hooks/auto_trace.sh` | **可能有 bug** — buffer 为空 |

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| 自动评分 (非会话内交互) | Claude Code hooks 不支持会话内交互提示 |
| auto_feedback 独立于 human_feedback | human 优先 auto 兜底，方便校准 |
| 评分 1-4 整数 | 与内置 "How is Claude doing" 一致 |

## Gotchas

- `.zshrc` / `settings.json` 在 don't-ask 模式下 Edit/Write 被拒
- `_PROJECT_ROUTES` 有缓存，改 config.yaml 后重启 Python
- 核心三文件规则：改 trace_engine/session_stop/feishu_notify 前必须有 test case
- 不要加功能，当前阶段是数据积累

## Services

| Service | Address |
|---------|---------|
| Dashboard | http://118.196.147.14/aw/ |
| Feedback API | http://118.196.147.14/aw/api/feedback?trace_id=xxx&rating=3 |

## Commands

```bash
aws                                    # 系统状态
awt                                    # 今天 traces
bash scripts/sync_to_server.sh         # 同步到服务器
cd scripts && python3 test_auto_rate.py # 跑测试
```
