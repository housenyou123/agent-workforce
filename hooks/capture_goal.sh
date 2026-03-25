#!/usr/bin/env bash
##############################################################################
# Agent Workforce — Capture Goal Hook (UserPromptSubmit)
#
# 捕获用户发送的第一条消息作为任务目标。
# 只保留第一条（后续追问不覆盖）。
##############################################################################

AW_DIR="$HOME/agent-workforce"
GOAL_FILE="$AW_DIR/traces/.current_goal"
PROMPT_COUNT_FILE="$AW_DIR/traces/.prompt_count"

mkdir -p "$AW_DIR/traces"

# 读取当前是第几条消息
COUNT=0
if [ -f "$PROMPT_COUNT_FILE" ]; then
    COUNT=$(cat "$PROMPT_COUNT_FILE" 2>/dev/null || echo "0")
fi
COUNT=$((COUNT + 1))
echo "$COUNT" > "$PROMPT_COUNT_FILE"

# 读 stdin 提取用户消息
INPUT=$(cat)
MESSAGE=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    # UserPromptSubmit 的 stdin 包含用户消息
    msg = d.get('message', d.get('prompt', d.get('content', '')))
    if isinstance(msg, str):
        # 截取前 200 字符作为 goal
        print(msg[:200])
    else:
        print(str(msg)[:200])
except:
    pass
" 2>/dev/null)

if [ -z "$MESSAGE" ]; then
    exit 0
fi

# 第一条消息 = 任务目标
if [ "$COUNT" -eq 1 ]; then
    echo "$MESSAGE" > "$GOAL_FILE"
fi

# 记录追问次数（供 Stop hook 使用）
echo "$COUNT" > "$PROMPT_COUNT_FILE"
