"""
Agent Workforce — Trace Engine

从 session_stop_trace.sh 抽出的核心逻辑:
1. 汇总 buffer 为完整 trace
2. 确定性验证 (build/lint/边界检查)
3. 成本估算 (按 token + 官网价格)
4. 持久化 (本地 JSONL + 远程 SQLite)
5. 飞书通知 (仅重要任务)
"""

import json
import os
import subprocess
import time
import urllib.request
from dataclasses import asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

from trace_schema import (
    new_trace, save_trace, ToolCall, detect_scenario,
    TRACES_DIR,
)
from feishu_notify import notify_task_complete

CST = timezone(timedelta(hours=8))
AW_DIR = Path.home() / "agent-workforce"
AW_SERVER = os.environ.get("AW_SERVER_URL", "http://118.196.147.14:9100")

# ─── Claude 官网价格 (USD per 1M tokens, 2026-03) ───
MODEL_PRICING = {
    "opus":   {"input": 15.0,  "output": 75.0},
    "sonnet": {"input": 3.0,   "output": 15.0},
    "haiku":  {"input": 0.25,  "output": 1.25},
}
DEFAULT_MODEL = "sonnet"


def estimate_cost(tool_calls: list[dict], model: str = DEFAULT_MODEL) -> dict:
    """
    从工具调用估算 token 成本

    估算逻辑:
    - Read/Glob/Grep: 主要消耗 input tokens (文件内容送入模型)
    - Edit/Write: 消耗 output tokens (模型生成代码)
    - Bash: 混合 (命令=output, 结果=input)
    - 每次工具调用有固定开销 (~200 tokens overhead)

    粗略但实用，后续可以从 Claude Code 的实际用量数据校准。
    """
    pricing = MODEL_PRICING.get(model, MODEL_PRICING[DEFAULT_MODEL])

    input_tokens = 0
    output_tokens = 0
    overhead_per_call = 200

    for call in tool_calls:
        tool = call.get("tool", "")
        target = call.get("target", "")

        if tool == "Read":
            # 读文件: 估算 ~50 tokens/行, 平均文件 100 行
            input_tokens += 5000
        elif tool in ("Edit", "Write"):
            # 写/改文件: output
            output_tokens += 2000
            input_tokens += 1000  # 看到旧内容
        elif tool == "Bash":
            output_tokens += 500  # 生成命令
            input_tokens += 2000  # 读取输出
        elif tool in ("Glob", "Grep"):
            input_tokens += 1000
        elif tool == "Agent":
            # sub-agent: 大量 token
            input_tokens += 20000
            output_tokens += 10000
        else:
            input_tokens += 500
            output_tokens += 500

        input_tokens += overhead_per_call

    total_cost = (
        input_tokens / 1_000_000 * pricing["input"]
        + output_tokens / 1_000_000 * pricing["output"]
    )

    return {
        "tokens_in": input_tokens,
        "tokens_out": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "estimated_cost_usd": round(total_cost, 4),
        "model": model,
    }


def run_verification(calls: list[dict], files_modified: list[str], cwd: str) -> dict:
    """
    确定性验证 — 从工具调用记录中提取验证结果

    返回:
      build_passed: bool | None
      lint_passed: bool | None
      files_in_boundary: bool
      credentials_safe: bool
    """
    result = {
        "build_passed": None,
        "lint_passed": None,
        "files_in_boundary": True,
        "credentials_safe": True,
    }

    # 1. Build 检查: 找最后一个 build 命令的结果
    for call in reversed(calls):
        if call.get("tool") == "Bash":
            cmd = call.get("target", "").lower()
            if any(k in cmd for k in ["build", "xcodebuild", "tsc", "next build", "vite build"]):
                exit_code = call.get("exit_code")
                if exit_code is not None:
                    result["build_passed"] = (exit_code == 0)
                else:
                    result["build_passed"] = None  # 旧 trace 没有 exit_code
                result["build_ran"] = True
                break

    # 2. Lint 检查
    for call in reversed(calls):
        if call.get("tool") == "Bash":
            cmd = call.get("target", "").lower()
            if any(k in cmd for k in ["lint", "eslint", "swiftlint", "prettier", "ruff"]):
                exit_code = call.get("exit_code")
                if exit_code is not None:
                    result["lint_passed"] = (exit_code == 0)
                else:
                    result["lint_passed"] = None
                result["lint_ran"] = True
                break

    # 3. 文件边界检查: 修改的文件是否都在 workdir 内
    cwd_resolved = os.path.realpath(os.path.expanduser(cwd))
    home_dir = os.path.realpath(str(Path.home()))
    allowed_prefixes = [
        cwd_resolved,                                    # 当前工作目录
        os.path.realpath(str(AW_DIR)),                   # agent-workforce 自身
        os.path.join(home_dir, ".claude"),                # Claude Code 配置/记忆
    ]
    for f in files_modified:
        f_resolved = os.path.realpath(os.path.expanduser(f))
        in_boundary = any(f_resolved.startswith(prefix) for prefix in allowed_prefixes)
        if not in_boundary:
            # 检查是否在 home 目录下 (宽松模式: 不出 home 就不算越界)
            if not f_resolved.startswith(home_dir):
                result["files_in_boundary"] = False
                break

    # 4. 凭据检查: 扫描修改的文件名
    import re
    credential_patterns = [".env", "credentials", ".pem", ".key", "secret"]
    for f in files_modified:
        fname = os.path.basename(f).lower()
        if any(p in fname for p in credential_patterns):
            result["credentials_safe"] = False
            break

    return result


def classify_session(
    duration_sec: float,
    tool_call_count: int,
    files_modified_count: int,
    prompt_count: int,
    verification: dict,
) -> str:
    """
    Session 分类: trivial / normal / significant / critical

    用于决定是否推飞书通知。
    """
    # critical: build 失败 或 凭据泄露 或 越界
    if verification.get("build_passed") is False:
        return "critical"
    if not verification.get("credentials_safe", True):
        return "critical"
    if not verification.get("files_in_boundary", True):
        return "critical"
    if prompt_count > 5 and duration_sec > 600:
        return "critical"

    # trivial: 纯查阅, 无修改, <2分钟
    if files_modified_count == 0 and duration_sec < 120:
        return "trivial"

    # significant: 多文件修改 或 耗时长
    if files_modified_count > 5 or duration_sec > 900:
        return "significant"

    return "normal"


def process_session(
    buffer_path: str,
    goal_path: str,
    prompt_count_path: str,
    session_start_path: str,
    cwd: str,
) -> dict | None:
    """
    处理一个完成的 session: 汇总 → 验证 → 计算成本 → 持久化 → 通知

    返回生成的 trace dict，或 None（无数据）
    """
    buffer = Path(buffer_path)
    if not buffer.exists() or buffer.stat().st_size == 0:
        return None

    # 1. 读取 buffer
    calls = []
    for line in buffer.read_text().strip().split("\n"):
        if line.strip():
            try:
                calls.append(json.loads(line))
            except:
                pass

    if not calls:
        return None

    # 2. 读取 goal
    goal = ""
    goal_file = Path(goal_path)
    if goal_file.exists():
        goal = goal_file.read_text().strip()
    if not goal:
        goal = f"(auto) session with {len(calls)} tool calls"

    # 3. 读取 prompt count
    prompt_count = 0
    pc_file = Path(prompt_count_path)
    if pc_file.exists():
        try:
            prompt_count = int(pc_file.read_text().strip())
        except:
            pass

    # 4. 计算 session 时长
    duration = 0
    ss_file = Path(session_start_path)
    if ss_file.exists():
        try:
            start_ts = int(ss_file.read_text().strip())
            duration = time.time() - start_ts
        except:
            pass
    if duration <= 0 and len(calls) >= 2:
        try:
            t0 = datetime.fromisoformat(calls[0]["ts"])
            t1 = datetime.fromisoformat(calls[-1]["ts"])
            duration = (t1 - t0).total_seconds()
        except:
            duration = 0

    # 5. 检测项目
    project, scenario, agent_id = detect_scenario(cwd)

    # 6. 统计文件变更
    files_modified = list(set(
        c.get("target", "") for c in calls
        if c.get("tool") in ("Edit", "Write") and c.get("target", "")
    ))
    files_read = list(set(
        c.get("target", "") for c in calls
        if c.get("tool") == "Read" and c.get("target", "")
    ))

    # 7. 确定性验证
    verification = run_verification(calls, files_modified, cwd)

    # 8. 成本估算
    cost = estimate_cost(calls, model=DEFAULT_MODEL)

    # 9. 构造 trace
    t = new_trace(
        goal=goal,
        project=project,
        scenario=scenario,
        agent_profile=f"{agent_id}_v1.0",
    )
    t.rounds = prompt_count
    t.tool_calls = [
        ToolCall(tool=c.get("tool", ""), target=c.get("target", "")[:100])
        for c in calls
    ]
    t.tool_call_count = len(calls)
    t.files_modified = files_modified[:20]
    t.context_files_read = files_read[:20]
    t.duration_sec = duration
    t.total_edits = sum(1 for c in calls if c.get("tool") in ("Edit", "Write"))
    t.retry_edits = max(0, t.total_edits - len(files_modified))
    t.build_success = verification.get("build_passed")
    t.lint_clean = verification.get("lint_passed")
    t.tokens_in = cost["tokens_in"]
    t.tokens_out = cost["tokens_out"]
    t.total_tokens = cost["total_tokens"]
    t.estimated_cost_usd = cost["estimated_cost_usd"]

    # 9b. Done Spec 结果 — 自动填充
    t.scope_respected = verification.get("files_in_boundary", True)
    t.verification_passed = (
        verification.get("build_passed") is not False
        and verification.get("lint_passed") is not False
        and verification.get("credentials_safe", True)
    )
    # deliverables_met: 有文件产出且验证通过
    t.deliverables_met = (
        len(files_modified) > 0
        and t.verification_passed
    )
    # completion_status
    if not t.scope_respected:
        t.completion_status = "failed"
    elif not verification.get("credentials_safe", True):
        t.completion_status = "failed"
    elif verification.get("build_passed") is False:
        t.completion_status = "failed"
    elif t.deliverables_met and t.verification_passed:
        t.completion_status = "completed"
    elif len(files_modified) == 0 and len(files_read) > 0:
        t.completion_status = "completed"  # 纯查阅也算完成
    else:
        t.completion_status = "completed_with_concern"

    # 9c. 双维度评分
    # Completion Score: 是否完成 (确定性)
    cs = 0.0
    if t.deliverables_met:
        cs += 0.35
    if t.verification_passed:
        cs += 0.35
    if t.scope_respected:
        cs += 0.15
    # contract_respected — 暂时默认 true (无 contract 机制)
    cs += 0.10
    # handoff_ready — 暂时默认 true
    cs += 0.05
    if not t.verification_passed:
        cs = min(cs, 0.59)  # Codex spec: verification 没过最高 0.59
    if not t.scope_respected:
        cs = 0.0  # 越界直接 0
    t.completion_score = round(cs, 2)

    # Quality Score: 完成质量 (混合信号)
    qs = 0.0
    # deterministic_checks (40%)
    det = 0.0
    if verification.get("build_passed") is True:
        det += 0.5
    elif verification.get("build_passed") is None:
        det += 0.25  # 没跑 build 给一半
    if verification.get("lint_passed") is True:
        det += 0.5
    elif verification.get("lint_passed") is None:
        det += 0.25
    qs += det * 0.40
    # review_result (20%) — 暂时默认 pass
    qs += 1.0 * 0.20
    # human_feedback (20%) — 需要后续填充
    fb = t.human_feedback
    if fb == "golden":
        qs += 1.0 * 0.20
    elif fb == "thumbs_up":
        qs += 0.8 * 0.20
    elif fb == "rework":
        qs += 0.4 * 0.20
    elif fb == "thumbs_down":
        qs += 0.0 * 0.20
    else:
        qs += 0.5 * 0.20  # 无反馈给中间值
    # implicit_signals (20%) — 暂时默认中等
    qs += 0.5 * 0.20
    t.quality_score = round(qs, 2)

    # 10. Session 分类
    tier = classify_session(
        duration, len(calls), len(files_modified), prompt_count, verification
    )

    # 11. 持久化 — 本地 JSONL
    save_trace(t)

    # 12. 持久化 — 远程服务端
    try:
        trace_data = asdict(t)
        trace_data["session_tier"] = tier
        trace_data["verification"] = verification
        payload = json.dumps(trace_data, ensure_ascii=False, default=str).encode("utf-8")
        req = urllib.request.Request(
            AW_SERVER + "/api/traces",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        # 服务端不可用时降级到本地，但记录失败原因（不静默吞掉）
        import logging
        logging.warning(f"[aw] server push failed: {e}")

    # 13. 飞书通知 — 只推 significant 和 critical
    if tier in ("significant", "critical"):
        try:
            # 生成文件变更摘要 (带行数)
            file_details = []
            for fpath in files_modified[:6]:
                fname = os.path.basename(fpath)
                try:
                    fdir = os.path.dirname(fpath) or cwd
                    stat = subprocess.run(
                        ["git", "diff", "--numstat", "HEAD", "--", fpath],
                        cwd=fdir, capture_output=True, text=True, timeout=3,
                    )
                    if stat.stdout.strip():
                        parts = stat.stdout.strip().split("\t")
                        added, deleted = int(parts[0]), int(parts[1])
                        if deleted == 0:
                            file_details.append(f"  · {fname} (+{added})")
                        elif added == 0:
                            file_details.append(f"  · {fname} (-{deleted})")
                        else:
                            file_details.append(f"  · {fname} (+{added}/-{deleted})")
                    else:
                        file_details.append(f"  · {fname}")
                except:
                    file_details.append(f"  · {fname}")

            if len(files_modified) > 6:
                file_details.append(f"  +{len(files_modified) - 6} files")

            files_str = "\n".join(file_details) if file_details else "no file changes"

            # 动作摘要
            bash_cmds = [c.get("target", "")[:50] for c in calls if c.get("tool") == "Bash"]
            key_cmds = [cmd for cmd in bash_cmds
                        if any(k in cmd.lower() for k in ["build", "test", "deploy", "install", "curl", "scp"])]
            action_parts = []
            if t.total_edits > 0:
                action_parts.append(f"edit {t.total_edits}")
            if key_cmds:
                action_parts.append(" / ".join(key_cmds[:2]))
            elif len(bash_cmds) > 0:
                action_parts.append(f"cmd {len(bash_cmds)}")
            action_str = " · ".join(action_parts) if action_parts else f"{len(calls)} tool calls"

            # 加入成本
            action_str += f" · ~${cost['estimated_cost_usd']:.2f}"

            # critical 加告警前缀
            card_goal = goal[:80] if goal and not goal.startswith("(auto)") else ""

            notify_task_complete(
                project=project,
                goal=card_goal,
                agent=f"{agent_id} v1.0",
                duration_sec=duration,
                cost_usd=cost["estimated_cost_usd"],
                trace_id=t.trace_id,
                files_summary=files_str,
                action_summary=action_str,
                review_verdict="fail" if tier == "critical" else "pass",
            )
        except:
            pass

    return {
        "trace_id": t.trace_id,
        "project": project,
        "tier": tier,
        "tool_calls": len(calls),
        "duration": duration,
        "cost_usd": cost["estimated_cost_usd"],
        "verification": verification,
    }


if __name__ == "__main__":
    # 测试
    import sys
    traces_dir = TRACES_DIR
    result = process_session(
        buffer_path=str(traces_dir / ".hook_buffer.jsonl"),
        goal_path=str(traces_dir / ".current_goal"),
        prompt_count_path=str(traces_dir / ".prompt_count"),
        session_start_path=str(traces_dir / ".session_start"),
        cwd=os.getcwd(),
    )
    if result:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("No data to process")
