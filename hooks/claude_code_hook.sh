#!/usr/bin/env bash
##############################################################################
# Agent Workforce — Claude Code Integration Hook
#
# 安装方法 (加到 ~/.zshrc):
#   source ~/agent-workforce/hooks/claude_code_hook.sh
#
# 功能:
#   1. aw_start  — 任务开始时调用 (自动检测项目)
#   2. aw_done   — 任务完成时调用 (自动采集 + 提示反馈)
#   3. aw_quick  — 一句话完成整个 log+feedback 流程
#   4. 快捷别名: aw1(👎) aw2(🔄) aw3(👍) aw4(⭐)
##############################################################################

AW_DIR="$HOME/agent-workforce"
AW_SCRIPTS="$AW_DIR/scripts"
AW_TRACES="$AW_DIR/traces"

# 当前会话状态
_AW_SESSION_START=""
_AW_SESSION_GOAL=""
_AW_SESSION_PROJECT=""
_AW_SESSION_AGENT=""

# ─── 颜色 ───
_aw_green='\033[0;32m'
_aw_yellow='\033[0;33m'
_aw_blue='\033[0;34m'
_aw_red='\033[0;31m'
_aw_gray='\033[0;37m'
_aw_bold='\033[1m'
_aw_reset='\033[0m'

# =========================================================================
# 核心函数
# =========================================================================

aw_start() {
    # 任务开始，记录起始时间 + 自动检测上下文
    _AW_SESSION_START=$(date +%s)
    _AW_SESSION_GOAL="${1:-}"

    # 自动检测 project 和 agent
    local detection
    detection=$(python3 -c "
import sys; sys.path.insert(0, '$AW_SCRIPTS')
from trace_schema import detect_scenario
p, s, a = detect_scenario('$PWD')
print(f'{p}|{s}|{a}')
" 2>/dev/null)

    _AW_SESSION_PROJECT=$(echo "$detection" | cut -d'|' -f1)
    local scenario=$(echo "$detection" | cut -d'|' -f2)
    _AW_SESSION_AGENT=$(echo "$detection" | cut -d'|' -f3)

    if [ -n "$_AW_SESSION_GOAL" ]; then
        echo -e "${_aw_blue}[aw]${_aw_reset} Session started: ${_aw_bold}$_AW_SESSION_PROJECT${_aw_reset} / $_AW_SESSION_AGENT"
    fi
}

aw_done() {
    # 任务完成，自动采集 + 交互式反馈
    local goal="${1:-$_AW_SESSION_GOAL}"
    local feedback=""

    if [ -z "$goal" ]; then
        echo -e "${_aw_yellow}[aw]${_aw_reset} Usage: aw_done \"任务描述\""
        return 1
    fi

    # 计算耗时
    local duration=0
    if [ -n "$_AW_SESSION_START" ]; then
        duration=$(( $(date +%s) - _AW_SESSION_START ))
    fi

    # 检测 git 变更
    local files_modified=""
    local build_ok=""
    if git rev-parse --is-inside-work-tree &>/dev/null; then
        files_modified=$(git diff --name-only HEAD 2>/dev/null | head -10 | tr '\n' ', ' | sed 's/,$//')
        # 如果有未提交的 swift 文件，尝试检测编译状态
        if echo "$files_modified" | grep -q "\.swift"; then
            build_ok="unknown"
        fi
    fi

    local project="${_AW_SESSION_PROJECT:-unknown}"
    local agent="${_AW_SESSION_AGENT:-unknown}"
    local agent_version="${agent}_v1.0"

    # 显示完成摘要
    echo ""
    echo -e "  ${_aw_green}┌─────────────────────────────────────────────┐${_aw_reset}"
    echo -e "  ${_aw_green}│${_aw_reset} ${_aw_bold}✅ Task Complete${_aw_reset} — $project"
    echo -e "  ${_aw_green}│${_aw_reset} Agent: $agent_version | ${duration}s"
    if [ -n "$files_modified" ]; then
        echo -e "  ${_aw_green}│${_aw_reset} Modified: ${_aw_gray}$files_modified${_aw_reset}"
    fi
    echo -e "  ${_aw_green}│${_aw_reset}"
    echo -e "  ${_aw_green}│${_aw_reset} Rate: ${_aw_bold}[Enter=skip] [1=👎] [2=🔄] [3=👍] [4=⭐]${_aw_reset}"
    echo -e "  ${_aw_green}└─────────────────────────────────────────────┘${_aw_reset}"
    echo ""

    # 读取反馈 (非阻塞，3秒超时)
    local rating=""
    read -t 10 -p "  > " rating

    case "$rating" in
        1) feedback="thumbs_down" ;;
        2) feedback="rework" ;;
        3) feedback="thumbs_up" ;;
        4) feedback="golden" ;;
        *) feedback="" ;;
    esac

    # 写入 trace
    python3 -c "
import sys, json
sys.path.insert(0, '$AW_SCRIPTS')
from trace_schema import new_trace, save_trace, ToolCall

t = new_trace(
    goal='''$goal''',
    project='$project',
    scenario='$(echo "$_AW_SESSION_AGENT" | sed "s/_agent//")',
    agent_profile='$agent_version',
)
t.duration_sec = $duration
t.files_modified = [f.strip() for f in '''$files_modified'''.split(',') if f.strip()]
t.human_feedback = '$feedback' if '$feedback' else None

path = save_trace(t)
print(f'trace_id={t.trace_id}')
" 2>/dev/null

    local feedback_display=""
    case "$feedback" in
        thumbs_up)   feedback_display="👍" ;;
        thumbs_down) feedback_display="👎" ;;
        rework)      feedback_display="🔄" ;;
        golden)      feedback_display="⭐" ;;
        *)           feedback_display="(skipped)" ;;
    esac

    echo -e "  ${_aw_blue}[aw]${_aw_reset} Logged ${feedback_display}"
    echo ""

    # 重置会话状态
    _AW_SESSION_START=""
    _AW_SESSION_GOAL=""
}

aw_quick() {
    # 一句话完成: aw_quick "做了XX" 3
    local goal="${1:-}"
    local rating="${2:-}"

    if [ -z "$goal" ]; then
        echo -e "${_aw_yellow}[aw]${_aw_reset} Usage: aw_quick \"任务描述\" [1-4]"
        return 1
    fi

    local feedback=""
    case "$rating" in
        1) feedback="thumbs_down" ;;
        2) feedback="rework" ;;
        3) feedback="thumbs_up" ;;
        4) feedback="golden" ;;
    esac

    # 自动检测
    local detection
    detection=$(python3 -c "
import sys; sys.path.insert(0, '$AW_SCRIPTS')
from trace_schema import detect_scenario
p, s, a = detect_scenario('$PWD')
print(f'{p}|{s}|{a}')
" 2>/dev/null)

    local project=$(echo "$detection" | cut -d'|' -f1)
    local scenario=$(echo "$detection" | cut -d'|' -f2)
    local agent=$(echo "$detection" | cut -d'|' -f3)

    python3 -c "
import sys
sys.path.insert(0, '$AW_SCRIPTS')
from trace_schema import new_trace, save_trace

t = new_trace(
    goal='''$goal''',
    project='$project',
    scenario='$scenario',
    agent_profile='${agent}_v1.0',
)
t.human_feedback = '$feedback' if '$feedback' else None
save_trace(t)
print(t.trace_id)
" 2>/dev/null

    local fb_emoji=""
    case "$feedback" in
        thumbs_up)   fb_emoji="👍" ;;
        thumbs_down) fb_emoji="👎" ;;
        rework)      fb_emoji="🔄" ;;
        golden)      fb_emoji="⭐" ;;
    esac

    echo -e "${_aw_blue}[aw]${_aw_reset} Logged: $project $fb_emoji"
}

# =========================================================================
# 快捷别名
# =========================================================================

# 快捷反馈 (用在 aw_done 之后补录，或者独立使用)
aw1() { aw_quick "${1:-last task}" 1; }  # 👎
aw2() { aw_quick "${1:-last task}" 2; }  # 🔄
aw3() { aw_quick "${1:-last task}" 3; }  # 👍
aw4() { aw_quick "${1:-last task}" 4; }  # ⭐

# 状态查看
alias aws='python3 ~/agent-workforce/cli.py status'
alias awt='python3 ~/agent-workforce/cli.py traces'
alias awr='python3 ~/agent-workforce/cli.py report'

# ─── 自动在 cd 时检测项目 ───
_aw_auto_detect() {
    # 如果进入了已知项目目录，静默设置上下文
    local detection
    detection=$(python3 -c "
import sys; sys.path.insert(0, '$AW_SCRIPTS')
from trace_schema import detect_scenario
p, s, a = detect_scenario('$PWD')
if p != 'unknown': print(f'{p}|{a}')
" 2>/dev/null)

    if [ -n "$detection" ]; then
        _AW_SESSION_PROJECT=$(echo "$detection" | cut -d'|' -f1)
        _AW_SESSION_AGENT=$(echo "$detection" | cut -d'|' -f2)
    fi
}

# Hook into cd
if [[ -n "$ZSH_VERSION" ]]; then
    autoload -U add-zsh-hook
    add-zsh-hook chpwd _aw_auto_detect
fi

# 首次加载时检测
_aw_auto_detect

# ─── claude 退出后自动评分提示 ───
_aw_post_claude() {
    local last_trace="$AW_DIR/traces/.last_trace_id"
    local last_url="$AW_DIR/traces/.last_feedback_url"

    if [ -f "$last_trace" ] && [ -s "$last_trace" ]; then
        local trace_id=$(cat "$last_trace")
        local feedback_url=$(cat "$last_url" 2>/dev/null)

        echo ""
        echo -e "  ${_aw_bold}[aw] Rate ${trace_id}:${_aw_reset} 1=bad  2=ok  3=good  4=golden  Enter=skip"
        read -t 15 -p "  > " rating

        if [ -n "$rating" ] && [ -n "$feedback_url" ]; then
            curl -sf "${feedback_url}&rating=${rating}" > /dev/null 2>&1
            local fb_emoji=""
            case "$rating" in
                1) fb_emoji="bad" ;;
                2) fb_emoji="ok" ;;
                3) fb_emoji="good" ;;
                4) fb_emoji="golden" ;;
            esac
            echo -e "  ${_aw_blue}[aw]${_aw_reset} ${fb_emoji}"
        fi

        # 清理
        > "$last_trace"
        > "$last_url"
    fi
}

echo -e "${_aw_blue}[aw]${_aw_reset} Agent Workforce loaded. Commands: aw_start, aw_done, aw_quick, aw1-4, aws, awt, awr"
