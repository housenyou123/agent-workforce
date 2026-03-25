"""
Agent Workforce — Nightly Evaluator (v2: 三层输出)

输出三层，不直接改 profile:
  Layer 1: Insight  — 发现 (自动存 knowledge/)
  Layer 2: Proposal — 提案 (推飞书等人类确认)
  Layer 3: Regression — 验证结果 (人类决定是否采纳)

运行:
  python evolution/nightly_eval.py --date 2026-03-25
  cron: 0 2 * * * cd ~/agent-workforce && python evolution/nightly_eval.py
"""

import argparse
import json
import os
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from trace_schema import load_traces, compute_auto_score
from feishu_notify import notify_nightly_report, notify_approval_request, notify_evolution

CST = timezone(timedelta(hours=8))
BASE_DIR = Path.home() / "agent-workforce"
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
REPORTS_DIR = BASE_DIR / "reports"

LOCAL_LLM_URL = os.environ.get("LOCAL_LLM_URL", "http://localhost:8801/v1/chat/completions")
LOCAL_LLM_MODEL = os.environ.get("LOCAL_LLM_MODEL", "qwen3.5-35b")


def call_local_llm(prompt: str, system: str = "", max_tokens: int = 2000) -> str:
    """调用本地 Qwen3.5-35B"""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = json.dumps({
        "model": LOCAL_LLM_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }).encode("utf-8")

    req = urllib.request.Request(
        LOCAL_LLM_URL, data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
            return result["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[eval] LLM call failed: {e}")
        return ""


# =========================================================================
# Layer 1: Insight (自动存储，不需要人类操作)
# =========================================================================

def generate_insights(traces: list[dict]) -> list[dict]:
    """从当天 traces 中提取 insights"""
    insights = []

    # 按 agent 分组统计
    agent_groups = defaultdict(list)
    for t in traces:
        agent = t.get("agent_profile", "unknown").rsplit("_v", 1)[0]
        agent_groups[agent].append(t)

    for agent_id, agent_traces in agent_groups.items():
        scores = []
        costs = []
        for t in agent_traces:
            score, _ = compute_auto_score(t)
            scores.append(score)
            costs.append(t.get("estimated_cost_usd", 0))

        avg_score = sum(scores) / len(scores) if scores else 0
        total_cost = sum(costs)
        success_rate = sum(1 for s in scores if s >= 0.7) / len(scores) if scores else 0

        # Insight: 成功率异常
        if success_rate < 0.6 and len(agent_traces) >= 3:
            insights.append({
                "type": "low_success_rate",
                "agent": agent_id,
                "value": round(success_rate, 2),
                "sample_size": len(agent_traces),
                "detail": f"{agent_id} 成功率 {success_rate:.0%} (基于 {len(agent_traces)} 个任务)",
            })

        # Insight: 成本异常
        avg_cost = total_cost / len(agent_traces) if agent_traces else 0
        if avg_cost > 0.50:
            insights.append({
                "type": "high_cost",
                "agent": agent_id,
                "value": round(avg_cost, 2),
                "detail": f"{agent_id} 平均成本 ${avg_cost:.2f}/任务",
            })

        # Insight: 高追问率
        high_followup = [t for t in agent_traces if t.get("rounds", 0) > 3]
        if len(high_followup) >= 2:
            insights.append({
                "type": "high_followup",
                "agent": agent_id,
                "value": len(high_followup),
                "detail": f"{agent_id} 有 {len(high_followup)} 个任务追问 >3 次",
            })

    # Insight: 确定性验证失败
    build_failures = [t for t in traces if t.get("build_success") is False]
    if build_failures:
        insights.append({
            "type": "build_failures",
            "value": len(build_failures),
            "detail": f"今日 {len(build_failures)} 个任务 build 失败",
            "traces": [t.get("trace_id") for t in build_failures],
        })

    # Insight: 高 retry_edits (对同一文件反复修改)
    high_retry = [t for t in traces if t.get("retry_edits", 0) > 3]
    if high_retry:
        insights.append({
            "type": "high_retry_edits",
            "value": len(high_retry),
            "detail": f"{len(high_retry)} 个任务反复编辑同一文件 >3 次",
        })

    return insights


def save_insights(date_str: str, insights: list[dict]):
    """存储 insights 到 knowledge/"""
    if not insights:
        return
    insight_dir = KNOWLEDGE_DIR / "insights"
    insight_dir.mkdir(parents=True, exist_ok=True)
    path = insight_dir / f"{date_str}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(insights, f, ensure_ascii=False, indent=2)


# =========================================================================
# Layer 2: Proposal (推飞书等人类确认)
# =========================================================================

def generate_proposals(insights: list[dict], traces: list[dict]) -> list[dict]:
    """基于 insights 生成改进提案 (不直接改 profile)"""
    proposals = []

    for insight in insights:
        if insight["type"] == "low_success_rate" and insight.get("sample_size", 0) >= 3:
            # 用 LLM 分析失败原因
            agent_id = insight["agent"]
            failures = [t for t in traces
                        if t.get("agent_profile", "").startswith(agent_id)
                        and compute_auto_score(t)[0] < 0.5]

            if failures:
                failure_goals = [{"goal": t.get("goal", "")[:100], "feedback": t.get("human_feedback")}
                                 for t in failures[:5]]

                llm_response = call_local_llm(
                    f"以下是 {agent_id} 的失败任务:\n{json.dumps(failure_goals, ensure_ascii=False)}\n\n"
                    f"请用一句话总结失败的共性原因，以及一条具体的改进建议。只输出 JSON: "
                    f'{{"root_cause": "...", "suggestion": "..."}}',
                    system="你是 AI Agent 评测专家。简洁回答。"
                )

                try:
                    start = llm_response.find("{")
                    end = llm_response.rfind("}") + 1
                    if start >= 0:
                        parsed = json.loads(llm_response[start:end])
                        proposals.append({
                            "type": "profile_improvement",
                            "agent": agent_id,
                            "insight_ref": insight["type"],
                            "root_cause": parsed.get("root_cause", ""),
                            "suggestion": parsed.get("suggestion", ""),
                            "evidence_count": len(failures),
                        })
                except:
                    pass

        elif insight["type"] == "high_cost":
            proposals.append({
                "type": "cost_optimization",
                "agent": insight["agent"],
                "suggestion": f"考虑对 {insight['agent']} 的低复杂度任务使用 Haiku 模型",
                "current_avg_cost": insight["value"],
            })

    return proposals


# =========================================================================
# Layer 3: Regression (人类决定后执行，现阶段不自动跑)
# =========================================================================

# 暂时只输出回归测试计划，不自动执行
# 等 golden examples 积累到 20+ 后再启用


# =========================================================================
# 主流程
# =========================================================================

def run_nightly_evaluation(date_str: str) -> dict:
    """执行夜间评测"""
    print(f"\n{'='*60}")
    print(f"  Nightly Evaluation — {date_str}")
    print(f"{'='*60}\n")

    # 加载 traces
    traces = load_traces(date_str)
    if not traces:
        print("[eval] No traces found.")
        return {"date": date_str, "status": "no_data"}

    print(f"[eval] {len(traces)} traces loaded")

    # Layer 1: Insights
    insights = generate_insights(traces)
    save_insights(date_str, insights)
    print(f"[eval] {len(insights)} insights generated")
    for i in insights:
        print(f"  - [{i['type']}] {i['detail']}")

    # Layer 2: Proposals (只在有 insight 时生成)
    proposals = generate_proposals(insights, traces)
    print(f"[eval] {len(proposals)} proposals generated")

    # 汇总统计
    agent_groups = defaultdict(list)
    for t in traces:
        agent = t.get("agent_profile", "unknown").rsplit("_v", 1)[0]
        agent_groups[agent].append(t)

    agent_stats = []
    for agent_id, agent_traces in agent_groups.items():
        costs = [t.get("estimated_cost_usd", 0) for t in agent_traces]
        completion_scores = [t.get("completion_score", 0.5) for t in agent_traces if t.get("completion_score") is not None]
        quality_scores = [t.get("quality_score", 0.5) for t in agent_traces if t.get("quality_score") is not None]
        completed = sum(1 for t in agent_traces if t.get("completion_status") == "completed")
        failed = sum(1 for t in agent_traces if t.get("completion_status") == "failed")

        agent_stats.append({
            "agent": agent_id,
            "tasks": len(agent_traces),
            "completed": completed,
            "failed": failed,
            "success_rate": round(completed / len(agent_traces), 2) if agent_traces else 0,
            "avg_completion": round(sum(completion_scores) / len(completion_scores), 2) if completion_scores else None,
            "avg_quality": round(sum(quality_scores) / len(quality_scores), 2) if quality_scores else None,
            "cost": round(sum(costs), 2),
        })

    # 生成报告
    total_cost = sum(t.get("estimated_cost_usd", 0) for t in traces)
    report = {
        "date": date_str,
        "summary": {
            "total_tasks": len(traces),
            "total_cost": round(total_cost, 2),
        },
        "agent_stats": agent_stats,
        "insights": insights,
        "proposals": proposals,
    }

    # 保存报告
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / f"{date_str}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n[eval] Report: {report_path}")

    # 推飞书: 日报
    overall_success = sum(s["success_rate"] * s["tasks"] for s in agent_stats) / len(traces) if traces else 0
    notify_nightly_report(
        date=date_str,
        total_tasks=len(traces),
        success_rate=overall_success,
        total_cost=total_cost,
        agent_stats=agent_stats,
        auto_upgrades=[],  # v2 不再自动升级
        pending_approvals=[p.get("suggestion", "")[:60] for p in proposals],
    )

    # 推飞书: 改进提案
    for p in proposals:
        notify_approval_request(
            request_type="proposal",
            title=f"{p.get('agent', '')} 改进提案",
            details=json.dumps(p, ensure_ascii=False, indent=2),
        )

    # 推飞书: insights 摘要
    if insights:
        insight_text = "\n".join(f"- {i['detail']}" for i in insights)
        notify_evolution(
            change_type="daily_insights",
            details=f"**{date_str} Insights ({len(insights)})**\n\n{insight_text}",
        )

    print(f"\n[eval] Done. {len(insights)} insights, {len(proposals)} proposals.")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Nightly Evaluator v2")
    parser.add_argument("--date", default=datetime.now(CST).strftime("%Y-%m-%d"))
    args = parser.parse_args()
    run_nightly_evaluation(args.date)
