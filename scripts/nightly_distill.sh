#!/usr/bin/env bash
##############################################################################
# Agent Workforce — Nightly Distill
#
# 每天自动: traces → SQLite + YAML + Obsidian vault
# 由 launchd 每晚 23:30 触发
##############################################################################

AW_DIR="$HOME/agent-workforce"
LOG="$AW_DIR/traces/.nightly_distill.log"

echo "$(date '+%Y-%m-%d %H:%M:%S') [distill] start" >> "$LOG"

# 1. 蒸馏 traces → YAML + SQLite
cd "$AW_DIR" && python3 evolution/distill_knowledge.py --apply >> "$LOG" 2>&1

# 2. 重新导入 Claude Memory (如果有新增/修改)
python3 -c "
import sys, json, os
sys.path.insert(0, '$AW_DIR/scripts')
from memory_db import MemoryDB
from pathlib import Path

MEMORY_DIR = Path.home() / '.claude/projects/-Users-housen/memory'
db = MemoryDB()
count = 0

for f in sorted(MEMORY_DIR.glob('*.md')):
    if f.name == 'MEMORY.md': continue
    fname = f.stem
    content = f.read_text().strip()
    if not content or len(content) < 50: continue

    mem_type = 'project'
    project = ''
    if '---' in content:
        parts = content.split('---')
        body = '---'.join(parts[2:]).strip() if len(parts) >= 3 else content
    else:
        body = content

    if 'feedback' in fname: mem_type = 'feedback'
    elif 'project' in fname:
        mem_type = 'project'
        project = fname.replace('project_', '')
    elif any(k in fname for k in ['deploy','infra','volcengine','vps']): mem_type = 'infra'
    elif 'user' in fname: mem_type = 'user'
    elif 'methodology' in fname: mem_type = 'methodology'
    elif 'desktop' in fname: mem_type = 'reference'

    importance = {'feedback':0.85,'user':0.9,'methodology':0.8,'infra':0.7}.get(mem_type, 0.65)

    db.save(type=mem_type, id=f'claude_memory_{fname}', content=body[:3000],
            project=project, importance=importance, tags=f'claude_memory,{mem_type},{fname}')
    count += 1

db.close()
print(f'Synced {count} Claude Memory entries')
" >> "$LOG" 2>&1

# 3. 导出到 Obsidian vault
python3 -c "
import sys, json
sys.path.insert(0, '$AW_DIR/scripts')
from memory_db import MemoryDB
from pathlib import Path

VAULT = Path('$AW_DIR/knowledge/vault')
db = MemoryDB()
rows = db.conn.execute('SELECT * FROM memories ORDER BY type, importance DESC').fetchall()

for r in rows:
    d = VAULT / r['type']
    d.mkdir(parents=True, exist_ok=True)
    safe_name = r['id'].replace('/', '_')[:60]
    path = d / f'{safe_name}.md'
    lines = [
        '---', f'type: {r[\"type\"]}', f'project: {r[\"project\"]}',
        f'agent: {r[\"agent\"]}', f'importance: {r[\"importance\"]}',
        f'access_count: {r[\"access_count\"]}', f'created: {r[\"created_at\"][:10]}',
        f'tags: {r[\"tags\"]}', '---', '', r['content'],
    ]
    path.write_text('\n'.join(lines), encoding='utf-8')

print(f'Exported {len(rows)} memories to Obsidian vault')
db.close()
" >> "$LOG" 2>&1

# 4. 时间衰减 (每周日额外跑)
if [ "$(date +%u)" = "7" ]; then
    cd "$AW_DIR/scripts" && python3 memory_db.py decay >> "$LOG" 2>&1
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') [distill] done" >> "$LOG"
