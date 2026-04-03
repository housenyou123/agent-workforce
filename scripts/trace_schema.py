"""
Agent Workforce — Trace Schema & Logger

Trace 是系统的核心数据结构，记录每次 Agent 任务的完整轨迹。
自动采集层 (Hook 写入) + 衍生计算层 (夜间离线算)。
"""

import json
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

# 北京时间
CST = timezone(timedelta(hours=8))
TRACES_DIR = Path.home() / "agent-workforce" / "traces"


@dataclass
class ToolCall:
    """单次工具调用记录"""
    tool: str                    # Read / Edit / Write / Bash / Glob / Grep
    target: str                  # 文件路径或命令摘要
    details: str = ""            # 行数 / exit_code 等
    timestamp: str = ""


@dataclass
class CrossReview:
    """交叉审查结果"""
    reviewer: str                # reviewer agent_id + version
    verdict: str                 # pass / concern / reject
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    auto_fixed: bool = False


@dataclass
class ImplicitSignals:
    """隐式反馈信号 (夜间从 trace + git 离线计算)"""
    output_committed: Optional[bool] = None
    commit_delay_min: Optional[float] = None
    human_post_edit_ratio: Optional[float] = None
    follow_up_count: int = 0
    goal_restated: bool = False
    frustration_detected: bool = False
    same_file_reopened_within_1h: bool = False
    task_abandoned: bool = False
    reverted: bool = False


@dataclass
class Trace:
    """一次 Agent 任务的完整轨迹"""

    # ─── 身份信息 ───
    trace_id: str = ""
    timestamp: str = ""
    project: str = ""
    scenario: str = ""            # ios_development / backend_api / web_frontend / data_analysis / infra

    # ─── 任务输入 ───
    goal: str = ""                        # 用户原始 prompt
    summary: str = ""                     # agent 实际做了什么 (从 tool calls 生成)
    goal_token_count: int = 0
    context_files_read: list[str] = field(default_factory=list)

    # ─── 执行过程 ───
    agent_profile: str = ""       # e.g. "ios_agent_v1.0"
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_count: int = 0
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    total_edits: int = 0
    retry_edits: int = 0          # 对同一文件的重复编辑

    # ─── 交叉 Review ───
    cross_review: Optional[CrossReview] = None

    # ─── 成本 ───
    tokens_in: int = 0
    tokens_out: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    duration_sec: float = 0.0
    rounds: int = 0               # 对话轮次

    # ─── Done Spec 输入 (任务开始前定义) ───
    deliverables: list[str] = field(default_factory=list)       # 需要交付什么
    verification: list[str] = field(default_factory=list)       # 如何验证完成
    constraints: list[str] = field(default_factory=list)        # 不能做什么
    completion_rule: str = ""                                    # 什么算完成

    # ─── Done Spec 结果 (任务完成后填充) ───
    deliverables_met: Optional[bool] = None      # 交付物是否齐全
    verification_passed: Optional[bool] = None   # 验证是否通过
    scope_respected: Optional[bool] = None       # 是否越界
    completion_status: str = ""                   # completed / completed_with_concern / blocked / failed

    # ─── 确定性验证 ───
    build_success: Optional[bool] = None
    test_pass: Optional[bool] = None
    lint_clean: Optional[bool] = None

    # ─── 双维度评分 ───
    completion_score: Optional[float] = None     # [0, 1] 是否完成
    quality_score: Optional[float] = None        # [0, 1] 完成质量

    # ─── 自动评分 ───
    auto_feedback: Optional[int] = None          # 1=bad 2=fine 3=good 4=golden (机器自评)

    # ─── 人类反馈 ───
    human_feedback: Optional[str] = None         # thumbs_up / thumbs_down / rework / golden
    failure_type: Optional[str] = None           # misunderstanding / poor_execution / scope_creep / broken_output / inefficient / external_blocker
    failure_note: Optional[str] = None

    # ─── 文件边界检测 ───
    boundary_violations: list[str] = field(default_factory=list)

    # ─── 工作目录 ───
    cwd: str = ""

    # ─── 隐式信号 (夜间计算) ───
    implicit_signals: Optional[ImplicitSignals] = None


def generate_trace_id() -> str:
    """生成 trace ID: tr_YYYYMMDD_NNN"""
    today = datetime.now(CST).strftime("%Y%m%d")
    traces_file = TRACES_DIR / f"{datetime.now(CST).strftime('%Y-%m-%d')}.jsonl"

    count = 0
    if traces_file.exists():
        with open(traces_file) as f:
            count = sum(1 for _ in f)

    return f"tr_{today}_{count + 1:03d}"


def new_trace(goal: str, project: str, scenario: str, agent_profile: str) -> Trace:
    """创建一个新的 Trace"""
    return Trace(
        trace_id=generate_trace_id(),
        timestamp=datetime.now(CST).isoformat(),
        goal=goal,
        goal_token_count=len(goal),  # 粗略用字符数代替 token 数
        project=project,
        scenario=scenario,
        agent_profile=agent_profile,
    )


def save_trace(trace: Trace) -> Path:
    """将 trace 追加到当天的 JSONL 文件"""
    TRACES_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(CST).strftime("%Y-%m-%d")
    traces_file = TRACES_DIR / f"{today}.jsonl"

    data = asdict(trace)
    # 清理 None 值减少文件体积
    data = {k: v for k, v in data.items() if v is not None}

    with open(traces_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False, default=str) + "\n")

    return traces_file


def load_traces(date_str: str) -> list[dict]:
    """加载指定日期的所有 traces"""
    traces_file = TRACES_DIR / f"{date_str}.jsonl"
    if not traces_file.exists():
        return []

    traces = []
    with open(traces_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                traces.append(json.loads(line))
    return traces


def compute_auto_score(trace: dict) -> tuple[float, str]:
    """
    根据隐式信号计算 auto_score

    返回: (score, confidence)
    score: 0.0 ~ 1.0
    confidence: low / medium / high
    """
    signals = trace.get("implicit_signals", {})
    if not signals:
        # 没有隐式信号，只用显式反馈
        feedback = trace.get("human_feedback")
        if feedback == "thumbs_up" or feedback == "golden":
            return 0.95, "medium"
        elif feedback == "thumbs_down":
            return 0.2, "medium"
        elif feedback == "rework":
            return 0.5, "medium"
        return 0.6, "low"  # 无任何反馈，给中等分

    score = 0.6  # 基线
    confidence_signals = 0

    # ─── 最强信号 (单独判定) ───
    if signals.get("reverted"):
        return 0.1, "high"
    if signals.get("task_abandoned"):
        return 0.2, "high"

    post_edit = signals.get("human_post_edit_ratio")
    if post_edit is not None:
        confidence_signals += 1
        if post_edit > 0.5:
            return 0.2, "high"
        elif post_edit < 0.05:
            score += 0.3
        elif post_edit < 0.15:
            score += 0.15
        else:
            score -= 0.1

    # ─── 强信号 ───
    if signals.get("output_committed"):
        confidence_signals += 1
        score += 0.1

    if trace.get("build_success") is False:
        score -= 0.3

    follow_up = signals.get("follow_up_count", 0)
    if follow_up > 3:
        score -= 0.2
        confidence_signals += 1
    elif follow_up == 0:
        score += 0.1
        confidence_signals += 1

    if signals.get("goal_restated"):
        score -= 0.15
        confidence_signals += 1

    if signals.get("frustration_detected"):
        score -= 0.2
        confidence_signals += 1

    # ─── 显式反馈覆盖 ───
    feedback = trace.get("human_feedback")
    if feedback == "thumbs_up" or feedback == "golden":
        score = max(score, 0.85)
        confidence_signals += 2
    elif feedback == "thumbs_down":
        score = min(score, 0.3)
        confidence_signals += 2

    # ─── 限制范围 ───
    score = max(0.0, min(1.0, score))

    # ─── 置信度 ───
    if confidence_signals >= 3:
        confidence = "high"
    elif confidence_signals >= 1:
        confidence = "medium"
    else:
        confidence = "low"

    return round(score, 2), confidence


# ─── 场景匹配 (从 config.yaml 读取，不再硬编码) ───

def _load_project_routes() -> dict:
    """从 config.yaml 加载 project_routes 映射"""
    import re
    config_path = Path.home() / "agent-workforce" / "config.yaml"
    if not config_path.exists():
        return {}

    routes = {}
    text = config_path.read_text()
    # 简单解析 project_routes 段落
    in_routes = False
    for line in text.split("\n"):
        if line.strip().startswith("project_routes:"):
            in_routes = True
            continue
        if in_routes and line and not line.startswith(" "):
            break  # 遇到下一个顶级 key
        if in_routes and '": {' in line:
            match = re.match(r'\s+"([^"]+)":\s*\{project:\s*"([^"]+)",\s*scenario:\s*"([^"]+)",\s*agent:\s*"([^"]+)"\}', line)
            if match:
                routes[match.group(1)] = (match.group(2), match.group(3), match.group(4))
    return routes

_PROJECT_ROUTES = None

# ─── 三级路由: Session 上下文继承 ───
_LAST_SESSION_ROUTE: tuple[str, str, str] | None = None


# ─── 三级路由: 内容关键词推断 ───
_CONTENT_KEYWORDS = {
    "enterprise-vpn": {
        "keywords": ["vpn", "shadowrocket", "wireguard", "xray", "proxy", "隧道", "503", "路由"],
        "scenario": "network_ops",
        "agent": "netops_agent",
    },
    "agent-workforce": {
        "keywords": ["agent workforce", "trace", "profile", "nightly", "evolution", "workforce"],
        "scenario": "infra",
        "agent": "infra_agent",
    },
    "spot-playground": {
        "keywords": ["spot playground", "spot-playground", "评测台", "评测平台", "benchmark", "eval platform", "玩法评测"],
        "scenario": "web_frontend",
        "agent": "web_agent",
    },
    "pixelbeat-ios": {
        "keywords": ["pixelbeat", "pixel beat", "paparazzi"],
        "scenario": "ios_development",
        "agent": "ios_agent",
    },
    "dog-story": {
        "keywords": ["dog story", "gossip dog", "八卦小狗", "sticker"],
        "scenario": "ios_development",
        "agent": "ios_agent",
    },
    "openclaw": {
        "keywords": ["openclaw", "飞书助手", "feishu bot"],
        "scenario": "backend_api",
        "agent": "backend_agent",
    },
    "interview-bot": {
        "keywords": ["interview", "面试", "简历", "resume", "候选人", "recruit", "招聘"],
        "scenario": "backend_api",
        "agent": "backend_agent",
    },
}


def detect_scenario(cwd: str, goal: str = "") -> tuple[str, str, str]:
    """
    三级路由: 从工作目录/上下文/内容推断 project, scenario, agent

    Level 1: 路径前缀匹配 (精确)
    Level 2: Session 继承 — 短指令沿用上一条的 project (同进程内)
    Level 3: 内容关键词推断 — 从 goal 文本推断

    Returns: (project_id, scenario, agent_id)
    """
    global _PROJECT_ROUTES, _LAST_SESSION_ROUTE
    if _PROJECT_ROUTES is None:
        _PROJECT_ROUTES = _load_project_routes()

    home = str(Path.home())
    rel = cwd.replace(home + "/", "")

    # Level 1: 路径前缀匹配
    for path_prefix, (project_id, scenario, agent_id) in _PROJECT_ROUTES.items():
        if rel.startswith(path_prefix):
            result = (project_id, scenario, agent_id)
            _LAST_SESSION_ROUTE = result
            return result

    # Level 2: Session 继承 — 短指令或 auto session 沿用上一条
    is_short = len(goal) <= 15 or goal.startswith("(auto)")
    if is_short and _LAST_SESSION_ROUTE is not None:
        return _LAST_SESSION_ROUTE

    # Level 3: 内容关键词推断
    if goal:
        goal_lower = goal.lower()
        for project_id, cfg in _CONTENT_KEYWORDS.items():
            if any(kw in goal_lower for kw in cfg["keywords"]):
                result = (project_id, cfg["scenario"], cfg["agent"])
                _LAST_SESSION_ROUTE = result
                return result

    # 未匹配到路由，返回 unknown，agent 由 trace_engine 根据文件类型推断
    return "unknown", "unknown", "unknown"


if __name__ == "__main__":
    # 测试
    t = new_trace(
        goal="给 PixelBeat 加 Instagram 分享功能",
        project="pixelbeat-ios",
        scenario="ios_development",
        agent_profile="ios_agent_v1.0",
    )
    t.tool_calls = [
        ToolCall(tool="Read", target="ShareView.swift", details="142 lines"),
        ToolCall(tool="Edit", target="ShareView.swift", details="3 changes"),
    ]
    t.tool_call_count = 2
    t.duration_sec = 94.5
    t.total_tokens = 16460
    t.build_success = True

    path = save_trace(t)
    print(f"Trace saved to {path}")
    print(json.dumps(asdict(t), ensure_ascii=False, indent=2))
