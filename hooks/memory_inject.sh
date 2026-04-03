#!/usr/bin/env bash
##############################################################################
# Agent Workforce — Memory + Skill Injection Hook (PreToolUse / session start)
#
# 在 session 的第一次工具调用前，从 SQLite 记忆库查询:
#   1. 相关经验 (lesson + pattern)
#   2. 可用技能 (从 memory.db type=pattern 或 knowledge/patterns/*.yaml)
# 并通过 systemMessage 注入到 Claude Code 上下文。
#
# 安装: 配置为 Claude Code PreToolUse hook (仅触发一次)
##############################################################################

AW_DIR="$HOME/agent-workforce"
AW_SCRIPTS="$AW_DIR/scripts"
INJECT_FLAG="$AW_DIR/traces/.memory_injected"

# 只在 session 的第一次工具调用时注入
if [ -f "$INJECT_FLAG" ]; then
    exit 0
fi

# 标记已注入
touch "$INJECT_FLAG"

# 从 stdin 读取 hook payload 获取上下文
MEMORY_TEXT=$(python3 -c "
import sys, json, os, glob
sys.path.insert(0, '$AW_SCRIPTS')

try:
    from memory_db import MemoryDB
    from trace_schema import detect_scenario
except ImportError:
    sys.exit(0)

# 检测当前项目
cwd = os.environ.get('PWD', os.getcwd())
project, scenario, agent = detect_scenario(cwd)

if project == 'unknown':
    sys.exit(0)

db = MemoryDB()
sections = []
char_budget = 2000
chars_used = 0

# ─── Section 1: 相关经验 (lesson + pattern) ───
memories = db.recall(project=project, agent=agent, limit=5, min_importance=0.3)
if not memories:
    memories = db.recall(project=project, limit=3, min_importance=0.5)

if memories:
    lines = ['## 相关经验 (自动注入)', '']
    for m in sorted(memories, key=lambda x: -x.get('importance', 0)):
        content = m['content']
        if len(content) > 150:
            content = content[:150] + '...'
        entry = f\"- [{m['type']}] {content}\"
        if chars_used + len(entry) > char_budget * 0.6:
            remaining = len(memories) - (len(lines) - 2)
            if remaining > 0:
                lines.append(f'- _(还有 {remaining} 条未展示)_')
            break
        lines.append(entry)
        chars_used += len(entry)
    sections.append('\n'.join(lines))

# ─── Section 2: 可用技能 (pattern memories + yaml patterns) ───
skills = []

# 2a: 从 memory.db 召回 type=pattern 的记忆 (agent 相关)
patterns = db.recall(agent=agent, type='pattern', limit=5, min_importance=0.2)
if not patterns:
    patterns = db.recall(type='pattern', limit=3, min_importance=0.3)

for p in patterns:
    # 提取 pattern name 和摘要
    content = p['content']
    # patterns 内容通常第一行是 pattern: xxx
    name = p.get('id', '').replace('pattern_', '')
    summary = content.split('\n')[0] if '\n' in content else content
    if summary.startswith('#'):
        summary = summary.lstrip('# ').strip()
    if len(summary) > 100:
        summary = summary[:100] + '...'
    skills.append(f'- {name}: {summary}')

# 2b: 从 knowledge/patterns/*.yaml 读取技能文件
pattern_dir = os.path.join('$AW_DIR', 'knowledge', 'patterns')
if os.path.isdir(pattern_dir):
    for yf in sorted(glob.glob(os.path.join(pattern_dir, '*.yaml')))[:5]:
        fname = os.path.basename(yf).replace('.yaml', '')
        try:
            with open(yf, 'r') as f:
                first_line = ''
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and not line.startswith('---'):
                        first_line = line
                        break
                if first_line and fname not in str(skills):
                    skills.append(f'- {fname}: {first_line}')
        except Exception:
            pass

if skills:
    skill_text = '\n'.join(['', '## 可用技能', ''] + skills[:8])
    if chars_used + len(skill_text) <= char_budget:
        sections.append(skill_text)
        chars_used += len(skill_text)

# ─── 输出 ───
if sections:
    print('\n'.join(sections))

db.close()
" 2>/dev/null)

# 如果有记忆要注入，通过 systemMessage 输出
if [ -n "$MEMORY_TEXT" ]; then
    # Escape for JSON
    ESCAPED=$(python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))" <<< "$MEMORY_TEXT")
    echo "{\"systemMessage\": $ESCAPED}"
fi
