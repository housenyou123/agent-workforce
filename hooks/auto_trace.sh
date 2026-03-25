#!/usr/bin/env bash
##############################################################################
# Agent Workforce — Auto Trace Hook (PostToolUse)
#
# 接收 stdin JSON: { tool_name, tool_input, tool_response }
# 提取: tool_name, target (文件路径或命令), exit_code (Bash 专有)
# 异步运行，不阻塞 Claude Code。
##############################################################################

AW_DIR="$HOME/agent-workforce"
LOG="$AW_DIR/traces/.hook_buffer.jsonl"
mkdir -p "$AW_DIR/traces"

# 读 stdin 一次，存到临时文件 (避免 shell 变量转义问题)
TMPFILE=$(mktemp)
cat > "$TMPFILE"

# 用一次 python 调用提取所有字段
RESULT=$(python3 -c "
import sys, json
try:
    with open('$TMPFILE') as f:
        d = json.load(f)
    tool = d.get('tool_name', '')
    ti = d.get('tool_input', {})
    tr = d.get('tool_response', {})

    # target: 文件路径 或 命令
    target = ''
    if isinstance(ti, dict):
        target = ti.get('file_path', '') or ti.get('path', '') or ti.get('command', '')[:100] or ti.get('pattern', '') or str(ti)[:80]
    else:
        target = str(ti)[:80]

    # exit_code: 只有 Bash 有
    exit_code = ''
    if tool == 'Bash' and isinstance(tr, dict):
        ec = tr.get('exit_code')
        if ec is not None:
            exit_code = str(ec)

    # 输出用 tab 分隔
    print(f'{tool}\t{target}\t{exit_code}')
except:
    print('\t\t')
" 2>/dev/null)

TOOL_NAME=$(echo "$RESULT" | cut -f1)
TOOL_TARGET=$(echo "$RESULT" | cut -f2)
EXIT_CODE=$(echo "$RESULT" | cut -f3)

TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%S+08:00)

# 构造 JSON (包含 exit_code)
if [ -n "$EXIT_CODE" ]; then
    echo "{\"ts\":\"$TIMESTAMP\",\"tool\":\"$TOOL_NAME\",\"target\":\"$TOOL_TARGET\",\"exit_code\":$EXIT_CODE}" >> "$LOG"
else
    echo "{\"ts\":\"$TIMESTAMP\",\"tool\":\"$TOOL_NAME\",\"target\":\"$TOOL_TARGET\"}" >> "$LOG"
fi

# 清理
rm -f "$TMPFILE"
