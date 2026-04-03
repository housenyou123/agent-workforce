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
    TRACES_DIR, _load_project_routes,
)
from feishu_notify import notify_task_complete

CST = timezone(timedelta(hours=8))
AW_DIR = Path.home() / "agent-workforce"
AW_SERVER = os.environ.get("AW_SERVER_URL", "http://118.196.147.14/aw")

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


def generate_summary(calls: list[dict], files_modified: list[str], files_read: list[str], goal: str) -> str:
    """
    从实际 tool calls 生成任务摘要，替代用户原始 prompt。

    输出示例:
      "修改 trace_engine.py, auto_trace.sh (编辑 5 处, build ok)"
      "排查 VPN: 执行 ssh, curl, ping (读 3 文件)"
      "(对话)"
    """
    if not calls:
        return "(对话)"

    # 提取关键信息
    edited_files = [os.path.basename(f) for f in files_modified[:4]]
    read_files = [os.path.basename(f) for f in files_read[:3]]
    edit_count = sum(1 for c in calls if c.get("tool") in ("Edit", "Write"))
    bash_cmds = [c.get("target", "")[:40] for c in calls if c.get("tool") == "Bash"]

    # 提取关键命令 (build/test/deploy/网络)
    key_cmds = []
    for cmd in bash_cmds:
        cmd_lower = cmd.lower()
        if any(k in cmd_lower for k in ["build", "xcodebuild", "tsc", "vite"]):
            key_cmds.append("build")
        elif any(k in cmd_lower for k in ["test", "jest", "pytest"]):
            key_cmds.append("test")
        elif any(k in cmd_lower for k in ["deploy", "scp", "rsync", "s3 sync"]):
            key_cmds.append("deploy")
        elif any(k in cmd_lower for k in ["curl", "ssh", "ping"]):
            key_cmds.append("网络检查")
        elif any(k in cmd_lower for k in ["git commit", "git push"]):
            key_cmds.append("git")
        elif any(k in cmd_lower for k in ["install", "pip", "npm"]):
            key_cmds.append("install")
    key_cmds = list(dict.fromkeys(key_cmds))  # 去重保序

    # 检查 build 结果
    build_result = ""
    for c in reversed(calls):
        if c.get("tool") == "Bash":
            cmd_lower = c.get("target", "").lower()
            if any(k in cmd_lower for k in ["build", "xcodebuild", "tsc"]):
                ec = c.get("exit_code")
                if ec == 0:
                    build_result = "build ok"
                elif ec is not None:
                    build_result = "build failed"
                break

    # 组装摘要
    parts = []

    if edited_files:
        files_str = ", ".join(edited_files)
        if len(files_modified) > 4:
            files_str += f" +{len(files_modified) - 4}"
        parts.append(f"修改 {files_str}")
    elif read_files and not bash_cmds:
        parts.append(f"查阅 {', '.join(read_files)}")

    details = []
    if edit_count > 0:
        details.append(f"编辑 {edit_count} 处")
    if build_result:
        details.append(build_result)

    if edited_files and details:
        # 有文件修改时，details 作为补充
        parts.append(f"({'; '.join(details)})")
    elif not edited_files and key_cmds:
        # 无文件修改时，key_cmds 作为主体
        pass  # 会在下面的 "not parts" 分支处理

    if not parts:
        # 只有 bash 命令没有文件操作
        if bash_cmds:
            if key_cmds:
                parts.append(f"执行: {', '.join(key_cmds)} ({len(bash_cmds)} 条命令)")
            else:
                # 取第一条有意义的命令作为摘要
                meaningful = [c[:50] for c in bash_cmds if len(c) > 3 and not c.startswith('#')]
                if meaningful:
                    parts.append(f"执行: {meaningful[0]}")
                else:
                    parts.append(f"执行 {len(bash_cmds)} 条命令")
        elif read_files:
            parts.append(f"查阅 {', '.join(read_files)}")
        else:
            return "(对话)"

    return " ".join(parts)


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


def auto_rate(
    completion_score: float,
    retry_edits: int,
    rounds: int,
    files_modified_count: int,
    verification: dict,
    tool_call_count: int = 0,
) -> int:
    """
    自动评分 v2: 1=bad 2=fine 3=good 4=golden

    基于确定性信号，不依赖人类反馈。
    v2 变化: 放宽 golden 条件 + 收紧 fine 条件 + 加入效率信号
    """
    # ─── 1 (bad): 硬性失败 ───
    if verification.get("build_passed") is False:
        return 1
    if not verification.get("credentials_safe", True):
        return 1
    if not verification.get("files_in_boundary", True):
        return 1

    # ─── 效率信号 ───
    efficiency_ratio = (tool_call_count / max(files_modified_count, 1)) if files_modified_count > 0 else 0

    # ─── 2 (fine): 有挣扎信号 ───
    if retry_edits > 2:
        return 2
    if rounds > 5:
        return 2
    # v2: 效率极低 (改1个文件用了15+次工具调用 且有 retry)
    if efficiency_ratio > 15 and retry_edits >= 1:
        return 2
    # v2: 有 retry 且对话轮次多
    if retry_edits >= 2 and rounds >= 3:
        return 2

    # ─── 4 (golden): 干净高效完成 ───
    # v2: 不再要求显式 build pass，而是看整体信号
    if retry_edits == 0 and files_modified_count >= 1:
        # 显式 build 通过 → 直接 golden
        if verification.get("build_passed") is True:
            return 4
        # 高效完成 (工具调用少、效率比合理)
        if efficiency_ratio <= 5 and tool_call_count <= 10:
            return 4
    # 纯诊断/查阅类: 0 文件修改但快速完成
    if files_modified_count == 0 and tool_call_count <= 3 and rounds <= 1:
        return 4

    # ─── 3 (good): 默认 ───
    return 3


def check_file_boundary(agent_id: str, files_modified: list[str]) -> list[str]:
    """
    P3: 检查修改的文件类型是否与 agent 匹配

    返回越界文件列表 (空=无越界)
    """
    AGENT_ALLOWED_EXTS = {
        "ios_agent": {".swift", ".xib", ".storyboard", ".plist", ".entitlements", ".xcconfig"},
        "backend_agent": {".go", ".ts", ".js", ".py", ".sql", ".json", ".yaml", ".yml"},
        "web_agent": {".tsx", ".ts", ".jsx", ".js", ".css", ".html", ".json", ".svg"},
        "data_agent": {".py", ".ipynb", ".csv", ".json", ".sql", ".parquet"},
        "infra_agent": {".sh", ".yaml", ".yml", ".conf", ".toml", ".py", ".json", ".md"},
        "netops_agent": {".go", ".conf", ".yaml", ".yml", ".sh", ".json", ".plist", ".md"},
    }
    allowed = AGENT_ALLOWED_EXTS.get(agent_id)
    if not allowed:
        return []

    violations = []
    for f in files_modified:
        ext = os.path.splitext(f)[1].lower()
        if ext and ext not in allowed:
            # .md files are universally allowed
            if ext != ".md":
                violations.append(os.path.basename(f))
    return violations


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

    # trivial: 无文件修改 且 工具调用少
    if files_modified_count == 0 and tool_call_count <= 3:
        return "trivial"

    # significant: 有文件修改 (核心变化: 改了文件 = 有价值)
    if files_modified_count >= 1:
        return "significant"

    # normal: 有工具调用但没改文件 (查阅、命令执行等)
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

    # 5. 检测项目 (三级路由: 路径 → session继承 → 内容推断)
    project, scenario, agent_id = detect_scenario(cwd, goal=goal)

    # 6. 统计文件变更
    files_modified = list(set(
        c.get("target", "") for c in calls
        if c.get("tool") in ("Edit", "Write") and c.get("target", "")
    ))
    files_read = list(set(
        c.get("target", "") for c in calls
        if c.get("tool") == "Read" and c.get("target", "")
    ))

    # 6b. 如果路由未匹配，从所有路径线索反推项目和 agent
    if project == "unknown":
        import re
        from collections import Counter

        home = str(Path.home())
        routes = _load_project_routes()

        # 收集所有路径线索: Edit/Write/Read targets + Bash 命令中的绝对路径
        all_paths = files_modified + files_read + [
            c.get("target", "") for c in calls
            if c.get("tool") in ("Edit", "Write", "Read") and c.get("target", "")
        ]
        # 从 Bash 命令 target 中提取 home 下的绝对路径
        for c in calls:
            if c.get("tool") == "Bash":
                cmd = c.get("target", "")
                all_paths.extend(re.findall(rf'{re.escape(home)}/[^\s\'";&|>]+', cmd))

        route_votes = Counter()
        for fpath in all_paths:
            rel = fpath.replace(home + "/", "")
            for path_prefix, route_val in routes.items():
                if rel.startswith(path_prefix):
                    route_votes[route_val] += 1
                    break
        if route_votes:
            best = route_votes.most_common(1)[0][0]
            project, scenario, agent_id = best

    if agent_id == "unknown" and files_modified:
        exts = [os.path.splitext(f)[1].lower() for f in files_modified]
        if any(e == ".swift" for e in exts):
            agent_id = "ios_agent"
            scenario = "ios_development"
        elif any(e in (".ts", ".tsx", ".jsx") for e in exts):
            basenames = [os.path.basename(f).lower() for f in files_modified]
            if any(k in n for n in basenames for k in ["view", "page", "component", "app.tsx", "index.tsx"]):
                agent_id = "web_agent"
                scenario = "web_frontend"
            else:
                agent_id = "backend_agent"
                scenario = "backend_api"
        elif any(e == ".py" for e in exts):
            agent_id = "data_agent"
            scenario = "data_analysis"
        elif any(e in (".sh", ".yaml", ".yml", ".conf", ".toml") for e in exts):
            agent_id = "infra_agent"
            scenario = "infra"
        elif any(e in (".go",) for e in exts):
            agent_id = "backend_agent"
            scenario = "backend_api"
        else:
            agent_id = "backend_agent"

    # 7. 确定性验证
    verification = run_verification(calls, files_modified, cwd)

    # 8. 成本估算
    cost = estimate_cost(calls, model=DEFAULT_MODEL)

    # 9. 构造 trace
    summary = generate_summary(calls, files_modified, files_read, goal)

    t = new_trace(
        goal=goal,
        project=project,
        scenario=scenario,
        agent_profile=f"{agent_id}_v1.0",
    )
    t.cwd = cwd
    t.summary = summary
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

    # 9c. 自动评分 (v2: 含效率信号)
    t.auto_feedback = auto_rate(
        completion_score=0,
        retry_edits=t.retry_edits,
        rounds=prompt_count,
        files_modified_count=len(files_modified),
        verification=verification,
        tool_call_count=len(calls),
    )

    # 9d. 文件类型边界检测 (P3: 交叉污染报警)
    t.boundary_violations = check_file_boundary(agent_id, files_modified)

    # 9e. 双维度评分
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

    # Quality Score: 完成质量 — 基于实际可用信号
    # 维度: 验证结果(25%) + 编辑效率(30%) + 执行效率(25%) + 反馈(20%)
    qs = 0.0

    # 1. 验证结果 (25%) — build/lint 显式结果权重高，None 不加分也不扣分
    det = 0.5  # 基线: 没跑验证给中等
    if verification.get("build_passed") is True:
        det = 1.0
    elif verification.get("build_passed") is False:
        det = 0.0
    if verification.get("lint_passed") is True:
        det = min(det + 0.2, 1.0)
    elif verification.get("lint_passed") is False:
        det = max(det - 0.2, 0.0)
    qs += det * 0.25

    # 2. 编辑效率 (30%) — retry_edits / total_edits 是最强的质量信号
    if t.total_edits > 0:
        retry_rate = t.retry_edits / t.total_edits
        if retry_rate == 0:
            edit_eff = 1.0    # 一次到位
        elif retry_rate <= 0.15:
            edit_eff = 0.8    # 轻微修正
        elif retry_rate <= 0.30:
            edit_eff = 0.55   # 明显挣扎
        elif retry_rate <= 0.50:
            edit_eff = 0.35   # 反复修改
        else:
            edit_eff = 0.15   # 严重问题
    else:
        edit_eff = 0.7  # 无编辑任务（查阅/命令），给中等偏上
    qs += edit_eff * 0.30

    # 3. 执行效率 (25%) — tool_call_count vs files_modified 的比例
    if len(files_modified) > 0 and t.tool_call_count > 0:
        # 理想: 每个文件 ~5 次工具调用 (读+改+验证)
        ratio = t.tool_call_count / max(len(files_modified), 1)
        if ratio <= 6:
            exec_eff = 1.0    # 精准高效
        elif ratio <= 12:
            exec_eff = 0.75   # 正常
        elif ratio <= 25:
            exec_eff = 0.50   # 偏多
        else:
            exec_eff = 0.25   # 大量试错
    elif t.tool_call_count <= 5:
        exec_eff = 0.8  # 轻量任务
    else:
        exec_eff = 0.6  # 纯命令执行，中等
    qs += exec_eff * 0.25

    # 4. 反馈 (20%) — 人类优先，auto_feedback 兜底
    fb = t.human_feedback
    if fb == "golden":
        fb_score = 1.0
    elif fb == "thumbs_up":
        fb_score = 0.9
    elif fb == "rework":
        fb_score = 0.35
    elif fb == "thumbs_down":
        fb_score = 0.0
    elif t.auto_feedback is not None:
        auto_map = {4: 1.0, 3: 0.8, 2: 0.4, 1: 0.0}
        fb_score = auto_map.get(t.auto_feedback, 0.5)
    else:
        fb_score = 0.5  # 无反馈给中等
    qs += fb_score * 0.20

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

            # 飞书显示 summary (agent 做了什么)，不显示用户原文
            notify_task_complete(
                project=project,
                goal=summary,
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
        "auto_feedback": t.auto_feedback,
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
