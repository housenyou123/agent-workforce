#!/usr/bin/env bash
##############################################################################
# Agent Workforce — Session Stop Hook
#
# Claude Code Stop hook: 调用 trace_engine.py 处理完成的 session
# 逻辑全部在 Python 模块中，bash 只负责调用和清理
##############################################################################

AW_DIR="$HOME/agent-workforce"
AW_TRACES="$AW_DIR/traces"
AW_SCRIPTS="$AW_DIR/scripts"
BUFFER="$AW_TRACES/.hook_buffer.jsonl"

# 无数据则跳过
if [ ! -s "$BUFFER" ]; then
    > "$AW_TRACES/.current_goal" 2>/dev/null
    echo "0" > "$AW_TRACES/.prompt_count" 2>/dev/null
    exit 0
fi

# 调用 trace_engine 处理
RESULT=$(python3 -c "
import sys, os, json
sys.path.insert(0, '$AW_SCRIPTS')
from trace_engine import process_session

result = process_session(
    buffer_path='$AW_TRACES/.hook_buffer.jsonl',
    goal_path='$AW_TRACES/.current_goal',
    prompt_count_path='$AW_TRACES/.prompt_count',
    session_start_path='$AW_TRACES/.session_start',
    cwd=os.environ.get('PWD', os.getcwd()),
)

if result:
    print(json.dumps(result, ensure_ascii=False))
" 2>/dev/null)

# 清理临时文件
> "$BUFFER"
> "$AW_TRACES/.current_goal" 2>/dev/null
echo "0" > "$AW_TRACES/.prompt_count" 2>/dev/null

# 输出结果
if [ -n "$RESULT" ]; then
    TRACE_ID=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('trace_id',''))" 2>/dev/null)
    TIER=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tier',''))" 2>/dev/null)
    COST=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('cost_usd',0))" 2>/dev/null)
    TRACE_COUNT=$(wc -l < "$AW_TRACES/$(date +%Y-%m-%d).jsonl" 2>/dev/null | tr -d ' ')

    FEEDBACK_BASE="http://118.196.147.14/aw/api/feedback?trace_id=${TRACE_ID}"

    if [ "$TIER" = "significant" ] || [ "$TIER" = "critical" ]; then
        # 有意义的 session: 通过 systemMessage 提示评分
        # additionalContext 让下一次 session 开始时 Claude 知道上一次的评分情况
        echo "{\"systemMessage\": \"[aw] ${TRACE_ID} (${TIER}) | Today: ${TRACE_COUNT:-0} | Rate: aw1=bad aw2=ok aw3=good aw4=golden\"}"

        # 同时写一个待评分文件，shell 快捷命令 aw1-4 读取
        echo "${TRACE_ID}" > "$AW_TRACES/.last_trace_id"
        echo "${FEEDBACK_BASE}" > "$AW_TRACES/.last_feedback_url"
    else
        echo "{\"systemMessage\": \"[aw] ${TRACE_ID} traced | Today: ${TRACE_COUNT:-0}\"}"
    fi
fi
