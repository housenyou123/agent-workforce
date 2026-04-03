#!/usr/bin/env bash
##############################################################################
# Agent Workforce — Auto Trace Hook (PostToolUse)
#
# 接收 stdin JSON，用 Python 提取字段并输出安全的 JSON 行到 buffer。
# 不在 shell 层拼接 JSON，避免转义问题。
##############################################################################

AW_DIR="$HOME/agent-workforce"
LOG="$AW_DIR/traces/.hook_buffer.jsonl"
mkdir -p "$AW_DIR/traces"

# 全部交给 Python 处理: 读 stdin → 提取字段 → json.dumps 输出 → 检测重复编辑
python3 -c "
import sys, json, os
from datetime import datetime, timezone, timedelta
from collections import Counter

try:
    d = json.load(sys.stdin)
except:
    sys.exit(0)

tool = d.get('tool_name', '')
if not tool:
    sys.exit(0)

ti = d.get('tool_input', {})
tr = d.get('tool_response', {})

# target
target = ''
if isinstance(ti, dict):
    target = ti.get('file_path', '') or ti.get('path', '') or (ti.get('command', '') or '')[:100] or ti.get('pattern', '') or ''
if not target and isinstance(ti, dict):
    target = str(ti)[:80]

# exit_code (Bash only)
exit_code = None
if tool == 'Bash' and isinstance(tr, dict):
    ec = tr.get('exit_code')
    if ec is not None:
        try:
            exit_code = int(ec)
        except:
            pass

# timestamp
ts = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%dT%H:%M:%S+08:00')

LOG = '$LOG'

# 构造 record
record = {'ts': ts, 'tool': tool, 'target': target}
if exit_code is not None:
    record['exit_code'] = exit_code

# json.dumps 保证安全转义
with open(LOG, 'a') as f:
    f.write(json.dumps(record, ensure_ascii=False) + '\n')

# === 重复编辑检测: 同文件第 3 次 Edit 时输出警告 ===
if tool in ('Edit', 'Write') and target:
    try:
        edit_counts = Counter()
        with open(LOG) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                if r.get('tool') in ('Edit', 'Write') and r.get('target'):
                    edit_counts[r['target']] += 1
        count = edit_counts.get(target, 0)
        if count == 3:
            fname = os.path.basename(target)
            print(f'⚠️ [{fname}] 已被编辑 3 次。建议: 重新 Read 全文件 + 检查 build error，再继续编辑。', file=sys.stderr)
        elif count == 5:
            fname = os.path.basename(target)
            print(f'🚨 [{fname}] 已被编辑 5 次! 强烈建议暂停，分析根因后再继续。', file=sys.stderr)
    except:
        pass
" 2>/dev/null
