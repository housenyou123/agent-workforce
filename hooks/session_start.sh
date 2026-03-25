#!/usr/bin/env bash
##############################################################################
# Agent Workforce — Session Start Hook
#
# Claude Code session 开始时：
# 1. 清空上一个 session 的临时文件
# 2. 记录开始时间
# 3. 检测项目上下文
##############################################################################

AW_DIR="$HOME/agent-workforce"
TRACES="$AW_DIR/traces"

mkdir -p "$TRACES"

# 清空上一个 session 的临时文件
> "$TRACES/.hook_buffer.jsonl" 2>/dev/null
> "$TRACES/.current_goal" 2>/dev/null
echo "0" > "$TRACES/.prompt_count" 2>/dev/null

# 记录开始时间
date +%s > "$TRACES/.session_start" 2>/dev/null
