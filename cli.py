#!/usr/bin/env python3
"""
Agent Workforce — CLI 入口

用法:
  python cli.py status                           # 查看所有 agent 状态
  python cli.py profiles                         # 列出所有 agent profile
  python cli.py traces [--date 2026-03-25]       # 查看当天 traces
  python cli.py evaluate [--date 2026-03-25]     # 手动触发夜间评测
  python cli.py report [--agent ios_agent] [--days 7]  # 查看 agent 报告
  python cli.py feedback <trace_id> <rating>     # 手动录入反馈
  python cli.py test-feishu                      # 测试飞书通知
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path.home() / "agent-workforce"
CST = timezone(timedelta(hours=8))

sys.path.insert(0, str(BASE_DIR / "scripts"))


def cmd_status(args):
    """查看所有 agent profile 的状态"""
    profiles_dir = BASE_DIR / "profiles"

    print("\n  Agent Workforce — Status")
    print("  " + "=" * 50)

    for agent_dir in sorted(profiles_dir.iterdir()):
        if not agent_dir.is_dir():
            continue

        yamls = sorted(agent_dir.glob("v*.yaml"), reverse=True)
        if not yamls:
            continue

        latest = yamls[0].stem
        golden_count = len(list((agent_dir / "golden_examples").glob("*.json"))) if (agent_dir / "golden_examples").exists() else 0

        print(f"\n  {agent_dir.name}")
        print(f"    Version:  {latest}")
        print(f"    Golden:   {golden_count} examples")
        print(f"    Profiles: {len(yamls)} versions")

    # 今日 traces
    today = datetime.now(CST).strftime("%Y-%m-%d")
    traces_file = BASE_DIR / "traces" / f"{today}.jsonl"
    trace_count = 0
    if traces_file.exists():
        with open(traces_file) as f:
            trace_count = sum(1 for _ in f)

    print(f"\n  Today ({today}): {trace_count} traces")

    # 最新报告
    reports_dir = BASE_DIR / "reports"
    reports = sorted(reports_dir.glob("*.json"), reverse=True)
    if reports:
        print(f"  Latest report: {reports[0].name}")
    else:
        print("  No reports yet")
    print()


def cmd_profiles(args):
    """列出所有 agent profile"""
    profiles_dir = BASE_DIR / "profiles"

    for agent_dir in sorted(profiles_dir.iterdir()):
        if not agent_dir.is_dir():
            continue

        yamls = sorted(agent_dir.glob("v*.yaml"))
        if not yamls:
            continue

        # 读取最新 profile 的基本信息
        try:
            import yaml
            with open(yamls[-1]) as f:
                profile = yaml.safe_load(f)
            name = profile.get("name", agent_dir.name)
            model = profile.get("model", "unknown")
            role_line = (profile.get("role") or "").strip().split("\n")[0][:60]
        except Exception:
            name = agent_dir.name
            model = "?"
            role_line = ""

        print(f"\n  {name} ({model})")
        print(f"    {role_line}")
        for y in yamls:
            print(f"    - {y.name}")


def cmd_traces(args):
    """查看指定日期的 traces"""
    from trace_schema import load_traces

    date = args.date or datetime.now(CST).strftime("%Y-%m-%d")
    traces = load_traces(date)

    if not traces:
        print(f"\n  No traces for {date}")
        return

    print(f"\n  Traces for {date} ({len(traces)} total)")
    print("  " + "-" * 70)

    for t in traces:
        score = t.get("auto_score", "?")
        feedback = t.get("human_feedback", "")
        fb_emoji = {"thumbs_up": "👍", "thumbs_down": "👎", "rework": "🔄", "golden": "⭐"}.get(feedback, "")
        agent = t.get("agent_profile", "?")
        goal = t.get("goal", "?")[:50]
        cost = t.get("estimated_cost_usd", 0)
        dur = t.get("duration_sec", 0)

        print(f"  {t.get('trace_id', '?'):20s} | {agent:20s} | {goal}")
        print(f"  {'':20s} | score: {score:>4} | ${cost:.2f} | {dur:.0f}s {fb_emoji}")


def cmd_evaluate(args):
    """手动触发夜间评测"""
    sys.path.insert(0, str(BASE_DIR / "evolution"))
    from nightly_eval import run_nightly_evaluation

    date = args.date or datetime.now(CST).strftime("%Y-%m-%d")
    run_nightly_evaluation(date)


def cmd_report(args):
    """查看 agent 报告"""
    reports_dir = BASE_DIR / "reports"
    days = args.days or 7

    # 收集最近 N 天的报告
    all_reports = []
    for i in range(days):
        d = (datetime.now(CST) - timedelta(days=i)).strftime("%Y-%m-%d")
        report_file = reports_dir / f"{d}.json"
        if report_file.exists():
            with open(report_file) as f:
                all_reports.append(json.load(f))

    if not all_reports:
        print(f"\n  No reports in the last {days} days")
        return

    agent_filter = args.agent

    print(f"\n  Agent Reports — Last {days} days")
    print("  " + "=" * 50)

    for report in all_reports:
        date = report.get("date", "?")
        summary = report.get("summary", {})
        print(f"\n  {date}: {summary.get('total_tasks', 0)} tasks | "
              f"success: {summary.get('success_rate', 0):.0%} | "
              f"cost: ${summary.get('total_cost', 0):.2f}")

        for a in report.get("agent_reports", []):
            if agent_filter and a["agent"] != agent_filter:
                continue
            sr = a.get("success_rate", 0)
            emoji = "✅" if sr >= 0.8 else ("⚠️" if sr >= 0.6 else "❌")
            print(f"    {a['agent']:20s} {a['tasks']:>3} tasks  {sr:.0%} {emoji}  ${a.get('cost', 0):.2f}")


def cmd_feedback(args):
    """手动录入反馈"""
    from trace_schema import load_traces, TRACES_DIR

    trace_id = args.trace_id
    rating = args.rating

    valid_ratings = ["thumbs_up", "thumbs_down", "rework", "golden"]
    if rating not in valid_ratings:
        print(f"  Invalid rating. Use one of: {', '.join(valid_ratings)}")
        return

    # 找到 trace 所在的文件
    today = datetime.now(CST).strftime("%Y-%m-%d")
    # trace_id 格式: tr_YYYYMMDD_NNN
    parts = trace_id.split("_")
    if len(parts) >= 2:
        date_str = f"{parts[1][:4]}-{parts[1][4:6]}-{parts[1][6:8]}"
    else:
        date_str = today

    traces_file = TRACES_DIR / f"{date_str}.jsonl"
    if not traces_file.exists():
        print(f"  Trace file not found: {traces_file}")
        return

    # 读取、更新、写回
    lines = traces_file.read_text().strip().split("\n")
    updated = False
    new_lines = []
    for line in lines:
        t = json.loads(line)
        if t.get("trace_id") == trace_id:
            t["human_feedback"] = rating
            updated = True
            print(f"  Updated {trace_id}: human_feedback = {rating}")
        new_lines.append(json.dumps(t, ensure_ascii=False))

    if updated:
        traces_file.write_text("\n".join(new_lines) + "\n")
    else:
        print(f"  Trace {trace_id} not found in {date_str}")


def cmd_test_feishu(args):
    """测试飞书通知"""
    from feishu_notify import notify_task_complete
    notify_task_complete(
        project="test",
        goal="测试飞书通知",
        agent="cli_test",
        duration_sec=1,
        cost_usd=0.0,
    )
    print("  Test message sent (check terminal output if webhook not configured)")


def main():
    parser = argparse.ArgumentParser(description="Agent Workforce CLI")
    subs = parser.add_subparsers(dest="command")

    subs.add_parser("status", help="查看系统状态")
    subs.add_parser("profiles", help="列出 agent profiles")

    p_traces = subs.add_parser("traces", help="查看 traces")
    p_traces.add_argument("--date", help="日期 YYYY-MM-DD")

    p_eval = subs.add_parser("evaluate", help="手动触发评测")
    p_eval.add_argument("--date", help="日期 YYYY-MM-DD")

    p_report = subs.add_parser("report", help="查看报告")
    p_report.add_argument("--agent", help="筛选 agent")
    p_report.add_argument("--days", type=int, help="天数")

    p_fb = subs.add_parser("feedback", help="录入反馈")
    p_fb.add_argument("trace_id", help="Trace ID")
    p_fb.add_argument("rating", help="thumbs_up / thumbs_down / rework / golden")

    subs.add_parser("test-feishu", help="测试飞书通知")

    args = parser.parse_args()

    commands = {
        "status": cmd_status,
        "profiles": cmd_profiles,
        "traces": cmd_traces,
        "evaluate": cmd_evaluate,
        "report": cmd_report,
        "feedback": cmd_feedback,
        "test-feishu": cmd_test_feishu,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
