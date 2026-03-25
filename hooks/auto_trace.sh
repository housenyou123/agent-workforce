#!/usr/bin/env bash
##############################################################################
# Agent Workforce — Auto Trace Hook
#
# Claude Code PostToolUse hook: 每次工具调用后自动追加到当天 trace 日志。
# 接收 stdin JSON: { tool_name, tool_input, tool_response }
# 异步运行，不阻塞 Claude Code。
##############################################################################

AW_DIR="$HOME/agent-workforce"
AW_TRACES="$AW_DIR/traces"
LOG="$AW_DIR/traces/.hook_buffer.jsonl"

mkdir -p "$AW_TRACES"

# 读 stdin
INPUT=$(cat)

# 提取关键字段
TOOL_NAME=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_name',''))" 2>/dev/null)
TOOL_INPUT=$(echo "$INPUT" | python3 -c "
import sys,json
d=json.load(sys.stdin)
ti = d.get('tool_input',{})
# 只保留关键信息，避免日志太大
if isinstance(ti, dict):
    fp = ti.get('file_path','') or ti.get('path','')
    cmd = ti.get('command','')[:100] if ti.get('command') else ''
    pattern = ti.get('pattern','')
    if fp: print(fp)
    elif cmd: print(cmd)
    elif pattern: print(pattern)
    else: print(str(ti)[:80])
else:
    print(str(ti)[:80])
" 2>/dev/null)

TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%S+08:00)

# 追加到 buffer（每个工具调用一条）
echo "{\"ts\":\"$TIMESTAMP\",\"tool\":\"$TOOL_NAME\",\"target\":\"$TOOL_INPUT\"}" >> "$LOG"
