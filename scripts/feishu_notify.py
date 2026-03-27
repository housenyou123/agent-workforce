"""
Agent Workforce — 飞书群通知模块

通过飞书群 Webhook 推送消息，支持:
- 任务完成通知 (#任务进展)
- 审批请求 (#审批请求)
- 每日报告 (#每日报告)
- 紧急告警 (#紧急告警)
- 进化记录 (#进化记录)

使用方式:
  1. 在飞书群中添加自定义机器人，获取 webhook URL
  2. 设置环境变量 FEISHU_WEBHOOK_URL
  3. 或在 config.yaml 中配置
"""

import json
import os
import urllib.request
import urllib.error
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Webhook URL 从环境变量读取
FEISHU_WEBHOOK_URL = os.environ.get("FEISHU_WEBHOOK_URL", "")
CONFIG_PATH = Path.home() / "agent-workforce" / "config.yaml"


def _get_webhook_url() -> str:
    """获取 webhook URL (环境变量 > config.yaml)"""
    if FEISHU_WEBHOOK_URL:
        return FEISHU_WEBHOOK_URL

    # 从 config.yaml 读取 (不依赖 pyyaml，用简单正则)
    if CONFIG_PATH.exists():
        import re
        text = CONFIG_PATH.read_text()
        match = re.search(r'webhook_url:\s*"([^"]+)"', text)
        if match:
            url = match.group(1)
            if url and not url.startswith("#"):
                return url

    return ""


def send_feishu_message(content: dict) -> bool:
    """
    发送飞书消息 (通过 webhook)

    Args:
        content: 飞书消息体 (Interactive Card 或 Text)

    Returns:
        是否发送成功
    """
    url = _get_webhook_url()
    if not url:
        print("[feishu] WARNING: FEISHU_WEBHOOK_URL not set, message not sent")
        print(f"[feishu] Message: {json.dumps(content, ensure_ascii=False, indent=2)}")
        return False

    payload = json.dumps(content, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            if result.get("code") == 0 or result.get("StatusCode") == 0:
                return True
            print(f"[feishu] API error: {result}")
            return False
    except urllib.error.URLError as e:
        print(f"[feishu] Network error: {e}")
        return False


# =========================================================================
# 消息模板
# =========================================================================

def notify_task_complete(
    project: str,
    goal: str,
    agent: str,
    duration_sec: float,
    cost_usd: float,
    review_verdict: str = "pass",
    reviewer: str = "",
    trace_id: str = "",
    files_summary: str = "",
    action_summary: str = "",
) -> bool:
    """任务完成通知 — 展示 agent 做了什么，而不是用户问了什么"""

    # 格式化耗时
    if duration_sec >= 60:
        time_str = f"{duration_sec / 60:.1f}min"
    else:
        time_str = f"{duration_sec:.0f}s"

    # 单层信息: project · agent · 耗时 + summary + 文件列表
    # goal 现在传入的就是 summary (从 tool calls 生成)
    content = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": "Task 完成"},
                "template": "green" if review_verdict == "pass" else "orange",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": (
                            f"**{project}** · {agent} · {time_str}"
                            + (f" · ~${cost_usd:.2f}" if cost_usd > 0 else "")
                            + (f"\n{files_summary}" if files_summary else "")
                        ),
                    },
                },
                {"tag": "hr"},
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": (
                            f"[满意](http://118.196.147.14/aw/api/feedback?trace_id={trace_id}&rating=3) | "
                            f"[还行](http://118.196.147.14/aw/api/feedback?trace_id={trace_id}&rating=2) | "
                            f"[不满意](http://118.196.147.14/aw/api/feedback?trace_id={trace_id}&rating=1) | "
                            f"[标杆](http://118.196.147.14/aw/api/feedback?trace_id={trace_id}&rating=4)"
                        ),
                    },
                },
            ],
        },
    }
    return send_feishu_message(content)


def notify_approval_request(
    request_type: str,
    title: str,
    details: str,
    options: list[dict] = None,
) -> bool:
    """审批请求 → #审批请求"""

    type_emoji = {
        "review_reject": "❌",
        "new_agent": "🆕",
        "rule_change": "📝",
        "deployment": "🚀",
        "mode_switch": "🔄",
        "destructive_op": "⚠️",
    }.get(request_type, "🔔")

    if options is None:
        options = [
            {"label": "✅ 同意", "value": "approve"},
            {"label": "❌ 拒绝", "value": "reject"},
            {"label": "💬 讨论", "value": "discuss"},
        ]

    actions = [
        {
            "tag": "button",
            "text": {"tag": "plain_text", "content": opt["label"]},
            "type": "primary" if opt["value"] == "approve" else ("danger" if opt["value"] == "reject" else "default"),
            "value": {"action": opt["value"]},
        }
        for opt in options
    ]

    content = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"{type_emoji} 需要你确认"},
                "template": "orange",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**类型**: {request_type}\n**{title}**\n\n{details}",
                    },
                },
                {"tag": "action", "actions": actions},
            ],
        },
    }
    return send_feishu_message(content)


def notify_nightly_report(
    date: str,
    total_tasks: int,
    success_rate: float,
    total_cost: float,
    agent_stats: list[dict],
    auto_upgrades: list[str] = None,
    pending_approvals: list[str] = None,
) -> bool:
    """夜间评测报告 → #每日报告"""

    stats_lines = []
    for s in agent_stats:
        emoji = "✅" if s["success_rate"] >= 0.8 else "⚠️"
        stats_lines.append(
            f"  {s['agent']:20s} {s['tasks']} tasks  "
            f"{s['success_rate']:.0%} {emoji}  ${s['cost']:.2f}"
        )
    stats_text = "\n".join(stats_lines)

    upgrades_text = ""
    if auto_upgrades:
        upgrades_text = "\n**自动升级**:\n" + "\n".join(f"  ✅ {u}" for u in auto_upgrades)

    pending_text = ""
    if pending_approvals:
        pending_text = "\n**待确认**:\n" + "\n".join(f"  ⚠️ {p}" for p in pending_approvals)

    content = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"📊 Nightly Report — {date}"},
                "template": "blue",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": (
                            f"**总览**: {total_tasks} 个任务 | "
                            f"成功率 {success_rate:.0%} | "
                            f"总成本 ${total_cost:.2f}\n\n"
                            f"**Agent 表现**:\n```\n{stats_text}\n```"
                            f"{upgrades_text}"
                            f"{pending_text}"
                        ),
                    },
                },
            ],
        },
    }
    return send_feishu_message(content)


def notify_alert(title: str, details: str, severity: str = "high") -> bool:
    """紧急告警 → #紧急告警"""

    template = "red" if severity == "high" else "orange"
    emoji = "🚨" if severity == "high" else "⚠️"

    content = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"{emoji} {title}"},
                "template": template,
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": details},
                },
            ],
        },
    }
    return send_feishu_message(content)


def notify_evolution(change_type: str, details: str) -> bool:
    """进化记录 → #进化记录"""

    type_emoji = {
        "profile_upgrade": "📈",
        "knowledge_added": "🧠",
        "routing_updated": "🔀",
        "rule_changed": "📝",
    }.get(change_type, "📋")

    content = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"{type_emoji} 进化记录"},
                "template": "purple",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**类型**: {change_type}\n\n{details}",
                    },
                },
            ],
        },
    }
    return send_feishu_message(content)


if __name__ == "__main__":
    # 测试 (不设 webhook 时会打印到终端)
    notify_task_complete(
        project="pixelbeat-ios",
        goal="给 StoryDetailView 加分享按钮",
        agent="ios_agent v1.0",
        duration_sec=94,
        cost_usd=0.12,
        review_verdict="pass",
        reviewer="backend_agent v1.0",
    )

    notify_nightly_report(
        date="2026-03-25",
        total_tasks=15,
        success_rate=0.87,
        total_cost=1.84,
        agent_stats=[
            {"agent": "ios_agent", "tasks": 8, "success_rate": 0.90, "cost": 0.98},
            {"agent": "backend_agent", "tasks": 4, "success_rate": 0.75, "cost": 0.62},
            {"agent": "web_agent", "tasks": 2, "success_rate": 1.0, "cost": 0.18},
            {"agent": "data_agent", "tasks": 1, "success_rate": 1.0, "cost": 0.06},
        ],
        auto_upgrades=["ios_agent v1.0 → v1.1 (增加 SwiftData 约束, 回归 +8%)"],
        pending_approvals=["backend_agent 工作流变更提案"],
    )
