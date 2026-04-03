"""
回填修复: 对已有 traces 重新计算 project 路由 + quality_score

用法:
  python scripts/recalc_traces.py                    # dry-run 显示变更
  python scripts/recalc_traces.py --apply             # 实际写入修改
  python scripts/recalc_traces.py --apply --date 2026-03-25  # 只处理指定日期
"""

import json
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from trace_schema import _load_project_routes, _CONTENT_KEYWORDS
from trace_engine import auto_rate, check_file_boundary

TRACES_DIR = Path.home() / "agent-workforce" / "traces"
HOME = str(Path.home())


def recalc_quality_score(t: dict) -> float:
    """用新公式重新计算 quality_score"""
    total_edits = t.get("total_edits", 0)
    retry_edits = t.get("retry_edits", 0)
    tool_call_count = t.get("tool_call_count", 0)
    files_mod_count = len(t.get("files_modified", []))
    build_passed = t.get("build_success")
    lint_passed = t.get("lint_clean")
    human_feedback = t.get("human_feedback")
    auto_feedback = t.get("auto_feedback")

    qs = 0.0

    # 1. 验证结果 (25%)
    det = 0.5
    if build_passed is True:
        det = 1.0
    elif build_passed is False:
        det = 0.0
    if lint_passed is True:
        det = min(det + 0.2, 1.0)
    elif lint_passed is False:
        det = max(det - 0.2, 0.0)
    qs += det * 0.25

    # 2. 编辑效率 (30%)
    if total_edits > 0:
        retry_rate = retry_edits / total_edits
        if retry_rate == 0:
            edit_eff = 1.0
        elif retry_rate <= 0.15:
            edit_eff = 0.8
        elif retry_rate <= 0.30:
            edit_eff = 0.55
        elif retry_rate <= 0.50:
            edit_eff = 0.35
        else:
            edit_eff = 0.15
    else:
        edit_eff = 0.7
    qs += edit_eff * 0.30

    # 3. 执行效率 (25%)
    if files_mod_count > 0 and tool_call_count > 0:
        ratio = tool_call_count / max(files_mod_count, 1)
        if ratio <= 6:
            exec_eff = 1.0
        elif ratio <= 12:
            exec_eff = 0.75
        elif ratio <= 25:
            exec_eff = 0.50
        else:
            exec_eff = 0.25
    elif tool_call_count <= 5:
        exec_eff = 0.8
    else:
        exec_eff = 0.6
    qs += exec_eff * 0.25

    # 4. 反馈 (20%)
    if human_feedback == "golden":
        fb_score = 1.0
    elif human_feedback == "thumbs_up":
        fb_score = 0.9
    elif human_feedback == "rework":
        fb_score = 0.35
    elif human_feedback == "thumbs_down":
        fb_score = 0.0
    elif auto_feedback is not None:
        auto_map = {4: 1.0, 3: 0.8, 2: 0.4, 1: 0.0}
        fb_score = auto_map.get(auto_feedback, 0.5)
    else:
        fb_score = 0.5
    qs += fb_score * 0.20

    return round(qs, 2)


def infer_project_from_paths(t: dict, routes: dict) -> tuple:
    """从 trace 的文件路径反推 project/scenario/agent"""
    all_paths = t.get("files_modified", []) + t.get("context_files_read", [])
    for tc in t.get("tool_calls", []):
        tool = tc.get("tool", "") if isinstance(tc, dict) else ""
        target = tc.get("target", "") if isinstance(tc, dict) else ""
        if tool in ("Edit", "Write", "Read") and target:
            all_paths.append(target)

    route_votes = Counter()
    for fpath in all_paths:
        rel = fpath.replace(HOME + "/", "")
        for path_prefix, route_val in routes.items():
            if rel.startswith(path_prefix):
                route_votes[route_val] += 1
                break

    if route_votes:
        return route_votes.most_common(1)[0][0]
    return None


def infer_project_from_goal(goal: str) -> tuple | None:
    """Level 3 路由: 从 goal 内容推断 project"""
    if not goal:
        return None
    goal_lower = goal.lower()
    for project_id, cfg in _CONTENT_KEYWORDS.items():
        if any(kw in goal_lower for kw in cfg["keywords"]):
            return (project_id, cfg["scenario"], cfg["agent"])
    return None


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Actually write changes")
    parser.add_argument("--date", help="Only process specific date (YYYY-MM-DD)")
    args = parser.parse_args()

    routes = _load_project_routes()

    if args.date:
        files = [TRACES_DIR / f"{args.date}.jsonl"]
    else:
        files = sorted(TRACES_DIR.glob("2026-*.jsonl"))

    stats = {
        "total": 0,
        "project_fixed": 0,
        "auto_feedback_backfilled": 0,
        "boundary_detected": 0,
        "quality_changed": 0,
        "project_changes": Counter(),
    }

    for trace_file in files:
        if not trace_file.exists():
            continue

        lines = trace_file.read_text().strip().split("\n")
        new_lines = []
        changed = False

        for line in lines:
            if not line.strip():
                new_lines.append(line)
                continue

            t = json.loads(line)
            stats["total"] += 1
            modified = False

            # Fix 1: Project routing (路径推断 + 内容推断)
            if t.get("project") == "unknown":
                # Level 2: 路径推断
                inferred = infer_project_from_paths(t, routes)
                # Level 3: 内容推断 (如果路径推断失败)
                if not inferred:
                    inferred = infer_project_from_goal(t.get("goal", ""))
                if inferred:
                    t["project"] = inferred[0]
                    t["scenario"] = inferred[1]
                    t["agent_profile"] = f"{inferred[2]}_v1.0"
                    stats["project_fixed"] += 1
                    stats["project_changes"][inferred[0]] += 1
                    modified = True

            # Fix 2: Recalc auto_feedback with v2 logic (always recalc)
            verification = {
                "build_passed": t.get("build_success"),
                "lint_passed": t.get("lint_clean"),
                "credentials_safe": True,
                "files_in_boundary": t.get("scope_respected", True),
            }
            new_af = auto_rate(
                completion_score=0,
                retry_edits=t.get("retry_edits", 0),
                rounds=t.get("rounds", 0),
                files_modified_count=len(t.get("files_modified", [])),
                verification=verification,
                tool_call_count=t.get("tool_call_count", 0),
            )
            if t.get("auto_feedback") != new_af:
                t["auto_feedback"] = new_af
                stats["auto_feedback_backfilled"] += 1
                modified = True

            # Fix 3: Boundary detection
            if "boundary_violations" not in t:
                agent = t.get("agent_profile", "").replace("_v1.0", "")
                violations = check_file_boundary(agent, t.get("files_modified", []))
                if violations:
                    t["boundary_violations"] = violations
                    stats["boundary_detected"] += 1
                    modified = True

            # Fix 4: Quality score recalc (with updated auto_feedback)
            new_qs = recalc_quality_score(t)
            old_qs = t.get("quality_score")
            if old_qs != new_qs:
                t["quality_score"] = new_qs
                stats["quality_changed"] += 1
                modified = True

            if modified:
                changed = True
            new_lines.append(json.dumps(t, ensure_ascii=False))

        if changed and args.apply:
            trace_file.write_text("\n".join(new_lines) + "\n")
            print(f"  [WRITE] {trace_file.name}")

    print(f"\n{'='*50}")
    print(f"总 traces: {stats['total']}")
    print(f"project 修复: {stats['project_fixed']}")
    if stats["project_changes"]:
        print(f"  修复后归属:")
        for proj, cnt in stats["project_changes"].most_common():
            print(f"    {proj}: {cnt}")
    print(f"auto_feedback 回补: {stats['auto_feedback_backfilled']}")
    print(f"boundary 越界检测: {stats['boundary_detected']}")
    print(f"quality_score 更新: {stats['quality_changed']}")
    if not args.apply:
        print(f"\n[DRY-RUN] 加 --apply 参数实际写入")


if __name__ == "__main__":
    main()
