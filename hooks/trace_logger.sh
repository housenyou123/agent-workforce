#!/usr/bin/env bash
##############################################################################
# Agent Workforce — Claude Code Hook: Trace Logger
#
# 在每次 Claude Code 任务结束后自动记录 trace。
# 通过 Claude Code 的 PostToolUse hook 或手动调用。
#
# 用法:
#   source ~/agent-workforce/hooks/trace_logger.sh
#   aw_log_trace "给 PixelBeat 加分享功能" "pixelbeat-ios" "ios_agent_v1.0"
#
# 自动检测:
#   - 从 $PWD 推断 project 和 scenario
#   - 从 git diff 检测修改的文件
#   - 从 git log 检测是否已 commit (隐式反馈)
##############################################################################

AW_DIR="$HOME/agent-workforce"
AW_TRACES_DIR="$AW_DIR/traces"
AW_SCRIPTS_DIR="$AW_DIR/scripts"

# 确保目录存在
mkdir -p "$AW_TRACES_DIR"

aw_log_trace() {
    local goal="${1:-}"
    local project="${2:-}"
    local agent="${3:-}"
    local feedback="${4:-}"  # 可选: thumbs_up / thumbs_down / rework / golden

    if [ -z "$goal" ]; then
        echo "[aw] Usage: aw_log_trace <goal> [project] [agent] [feedback]"
        return 1
    fi

    local today
    today=$(date +%Y-%m-%d)
    local trace_file="$AW_TRACES_DIR/$today.jsonl"

    # 自动推断 project/scenario
    if [ -z "$project" ]; then
        project=$(python3 -c "
import sys; sys.path.insert(0, '$AW_SCRIPTS_DIR')
from trace_schema import detect_scenario
p, s, a = detect_scenario('$PWD')
print(p)
" 2>/dev/null || echo "unknown")
    fi

    if [ -z "$agent" ]; then
        agent=$(python3 -c "
import sys; sys.path.insert(0, '$AW_SCRIPTS_DIR')
from trace_schema import detect_scenario
p, s, a = detect_scenario('$PWD')
print(a + '_v1.0')
" 2>/dev/null || echo "unknown_v1.0")
    fi

    # 检测 git 状态
    local files_modified=""
    local committed="false"
    if git rev-parse --is-inside-work-tree &>/dev/null; then
        files_modified=$(git diff --name-only HEAD 2>/dev/null | head -20 | tr '\n' ',' | sed 's/,$//')
        # 检查最近 5 分钟内是否有 commit
        local recent_commit
        recent_commit=$(git log --since="5 minutes ago" --oneline 2>/dev/null | head -1)
        if [ -n "$recent_commit" ]; then
            committed="true"
        fi
    fi

    # 生成 trace ID
    local count
    count=$(wc -l < "$trace_file" 2>/dev/null || echo "0")
    count=$((count + 1))
    local trace_id="tr_$(date +%Y%m%d)_$(printf '%03d' "$count")"

    # 写入 trace
    local timestamp
    timestamp=$(date -u +%Y-%m-%dT%H:%M:%S+08:00)

    local trace_json
    trace_json=$(cat <<TRACE_EOF
{"trace_id":"$trace_id","timestamp":"$timestamp","project":"$project","agent_profile":"$agent","goal":"$goal","files_modified":[$(echo "$files_modified" | sed 's/[^,]*/\"&\"/g')],"human_feedback":"$feedback","implicit_signals":{"output_committed":$committed}}
TRACE_EOF
)

    echo "$trace_json" >> "$trace_file"
    echo "[aw] Trace logged: $trace_id ($project)"
}

# 快捷反馈函数
aw_good() { aw_log_trace "${1:-last task}" "" "" "thumbs_up"; }
aw_bad() { aw_log_trace "${1:-last task}" "" "" "thumbs_down"; }
aw_rework() { aw_log_trace "${1:-last task}" "" "" "rework"; }
aw_golden() { aw_log_trace "${1:-last task}" "" "" "golden"; }

# 快捷状态查看
aw_status() { python3 "$AW_DIR/cli.py" status; }
aw_today() { python3 "$AW_DIR/cli.py" traces; }
