"""
Agent Workforce — SQLite Long-Term Memory

可查询的记忆库，从 knowledge/ YAML 蒸馏写入。
FTS5 全文检索 + 时间衰减 + citation 验证 + 重要性评分。

零外部依赖 (纯 Python sqlite3)。

用法:
  from memory_db import MemoryDB
  db = MemoryDB()
  db.save("lesson", project="enterprise-vpn", agent="netops_agent",
          content="503 排查: nginx upstream → 服务进程 → iptables",
          citations=[{"file": "shadowrocket.go", "lines": [145, 210]}])
  results = db.search("VPN 503 排查")
  results = db.recall(project="enterprise-vpn", limit=5)
"""

import json
import math
import os
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

CST = timezone(timedelta(hours=8))
DB_PATH = Path.home() / "agent-workforce" / "knowledge" / "memory.db"


class MemoryDB:
    def __init__(self, db_path: str | Path = DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,          -- lesson / pattern / decision / agent_profile / project_profile
                project TEXT DEFAULT '',
                agent TEXT DEFAULT '',
                content TEXT NOT NULL,
                citations TEXT DEFAULT '[]',  -- JSON array of {file, lines, commit}
                source_traces TEXT DEFAULT '[]', -- JSON array of trace_ids
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_accessed TEXT NOT NULL,
                access_count INTEGER DEFAULT 0,
                importance REAL DEFAULT 0.5,  -- 0.0-1.0
                tags TEXT DEFAULT ''          -- comma-separated
            );

            CREATE INDEX IF NOT EXISTS idx_memories_project ON memories(project);
            CREATE INDEX IF NOT EXISTS idx_memories_agent ON memories(agent);
            CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(type);
            CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance DESC);
        """)

        # FTS5 virtual table for full-text search
        # Check if it exists first
        row = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='fts_memories'"
        ).fetchone()
        if not row:
            self.conn.execute("""
                CREATE VIRTUAL TABLE fts_memories USING fts5(
                    id, content, project, agent, tags,
                    tokenize='unicode61'
                )
            """)

        self.conn.commit()

    # ─── CRUD ───

    def save(
        self,
        type: str,
        content: str,
        *,
        id: str = "",
        project: str = "",
        agent: str = "",
        citations: list[dict] | None = None,
        source_traces: list[str] | None = None,
        importance: float = 0.5,
        tags: str = "",
    ) -> str:
        """保存一条记忆。如果 id 已存在则更新。"""
        now = datetime.now(CST).isoformat()
        if not id:
            # Auto-generate id: type_project_hash
            import hashlib
            h = hashlib.md5(f"{type}:{project}:{content[:100]}".encode()).hexdigest()[:8]
            id = f"{type}_{project}_{h}" if project else f"{type}_{h}"

        citations_json = json.dumps(citations or [], ensure_ascii=False)
        traces_json = json.dumps(source_traces or [], ensure_ascii=False)

        existing = self.conn.execute("SELECT id FROM memories WHERE id = ?", (id,)).fetchone()

        if existing:
            self.conn.execute("""
                UPDATE memories SET content=?, citations=?, source_traces=?,
                    updated_at=?, importance=?, tags=?, project=?, agent=?
                WHERE id=?
            """, (content, citations_json, traces_json, now, importance, tags, project, agent, id))
            # Update FTS
            self.conn.execute("DELETE FROM fts_memories WHERE id=?", (id,))
        else:
            self.conn.execute("""
                INSERT INTO memories (id, type, project, agent, content, citations,
                    source_traces, created_at, updated_at, last_accessed, access_count,
                    importance, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
            """, (id, type, project, agent, content, citations_json,
                  traces_json, now, now, now, importance, tags))

        # Update FTS index
        self.conn.execute("""
            INSERT INTO fts_memories (id, content, project, agent, tags)
            VALUES (?, ?, ?, ?, ?)
        """, (id, content, project, agent, tags))

        self.conn.commit()
        return id

    def delete(self, id: str):
        self.conn.execute("DELETE FROM memories WHERE id = ?", (id,))
        self.conn.execute("DELETE FROM fts_memories WHERE id = ?", (id,))
        self.conn.commit()

    # ─── 查询 ───

    def search(self, query: str, *, limit: int = 10, project: str = "", agent: str = "") -> list[dict]:
        """
        FTS5 全文搜索。返回按相关性排序的记忆列表。
        每次搜索自动更新 access_count 和 last_accessed。
        """
        # Build FTS query with optional filters
        fts_query = query
        if project:
            fts_query += f" AND project:{project}"
        if agent:
            fts_query += f" AND agent:{agent}"

        try:
            rows = self.conn.execute("""
                SELECT m.*, rank
                FROM fts_memories f
                JOIN memories m ON f.id = m.id
                WHERE fts_memories MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (fts_query, limit)).fetchall()
        except sqlite3.OperationalError:
            # Fallback: simple LIKE search if FTS query syntax fails
            rows = self.conn.execute("""
                SELECT *, 0 as rank FROM memories
                WHERE content LIKE ?
                AND (? = '' OR project = ?)
                AND (? = '' OR agent = ?)
                ORDER BY importance DESC
                LIMIT ?
            """, (f"%{query}%", project, project, agent, agent, limit)).fetchall()

        results = [dict(r) for r in rows]

        # Update access metadata
        now = datetime.now(CST).isoformat()
        for r in results:
            self.conn.execute("""
                UPDATE memories SET access_count = access_count + 1,
                    last_accessed = ? WHERE id = ?
            """, (now, r["id"]))
        self.conn.commit()

        return results

    def recall(
        self,
        *,
        project: str = "",
        agent: str = "",
        type: str = "",
        limit: int = 10,
        min_importance: float = 0.0,
    ) -> list[dict]:
        """
        按 project/agent/type 召回记忆，按 importance 排序。
        用于 session 开始时的上下文注入。
        """
        conditions = ["importance >= ?"]
        params: list = [min_importance]

        if project:
            conditions.append("project = ?")
            params.append(project)
        if agent:
            conditions.append("agent = ?")
            params.append(agent)
        if type:
            conditions.append("type = ?")
            params.append(type)

        where = " AND ".join(conditions)
        params.append(limit)

        rows = self.conn.execute(f"""
            SELECT * FROM memories
            WHERE {where}
            ORDER BY importance DESC, access_count DESC
            LIMIT ?
        """, params).fetchall()

        results = [dict(r) for r in rows]

        # Update access
        now = datetime.now(CST).isoformat()
        for r in results:
            self.conn.execute("""
                UPDATE memories SET access_count = access_count + 1,
                    last_accessed = ? WHERE id = ?
            """, (now, r["id"]))
        self.conn.commit()

        return results

    # ─── 时间衰减 ───

    def decay_importance(self, half_life_days: int = 30):
        """
        时间衰减: importance 随时间指数衰减，高频访问可抵消衰减。

        公式: new_importance = base * 0.5^(days/half_life) + access_boost
        access_boost = min(0.2, access_count * 0.01)
        """
        now = datetime.now(CST)
        rows = self.conn.execute("SELECT id, importance, last_accessed, access_count FROM memories").fetchall()

        updated = 0
        for r in rows:
            try:
                last = datetime.fromisoformat(r["last_accessed"])
                days = (now - last).total_seconds() / 86400
            except (ValueError, TypeError):
                days = 30

            decay = 0.5 ** (days / half_life_days)
            access_boost = min(0.2, r["access_count"] * 0.01)
            new_importance = max(0.05, min(1.0, r["importance"] * decay + access_boost))

            if abs(new_importance - r["importance"]) > 0.01:
                self.conn.execute(
                    "UPDATE memories SET importance = ? WHERE id = ?",
                    (round(new_importance, 3), r["id"])
                )
                updated += 1

        self.conn.commit()
        return updated

    # ─── Citation 验证 ───

    def verify_citations(self, id: str) -> dict:
        """
        验证记忆中的 citation 是否仍然有效。
        返回 {"valid": [...], "stale": [...], "missing": [...]}
        """
        row = self.conn.execute("SELECT citations FROM memories WHERE id = ?", (id,)).fetchone()
        if not row:
            return {"valid": [], "stale": [], "missing": []}

        citations = json.loads(row["citations"])
        result = {"valid": [], "stale": [], "missing": []}

        for c in citations:
            fpath = c.get("file", "")
            if not fpath:
                continue

            # Try to find file
            if os.path.exists(fpath):
                result["valid"].append(c)
            else:
                # Try relative to home
                home_path = Path.home() / fpath
                if home_path.exists():
                    result["valid"].append(c)
                else:
                    result["missing"].append(c)

        return result

    # ─── 格式化输出 ───

    def format_for_injection(
        self,
        memories: list[dict],
        max_chars: int = 2000,
    ) -> str:
        """
        把记忆格式化为可注入 Claude Code session 的文本。
        控制在 max_chars 内，优先展示高 importance 的。
        """
        if not memories:
            return ""

        lines = ["## 相关经验 (从记忆库自动注入)", ""]
        total = 0

        for m in sorted(memories, key=lambda x: -x.get("importance", 0)):
            content = m["content"]
            # Truncate long content
            if len(content) > 200:
                content = content[:200] + "..."

            entry = f"- **[{m['type']}]** {content}"
            if m.get("project"):
                entry += f" _(project: {m['project']})_"

            if total + len(entry) > max_chars:
                lines.append(f"- _(还有 {len(memories) - len(lines) + 2} 条记忆未展示)_")
                break

            lines.append(entry)
            total += len(entry)

        return "\n".join(lines)

    # ─── 统计 ───

    def stats(self) -> dict:
        """返回记忆库统计信息"""
        total = self.conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        by_type = dict(self.conn.execute(
            "SELECT type, COUNT(*) FROM memories GROUP BY type"
        ).fetchall())
        by_project = dict(self.conn.execute(
            "SELECT project, COUNT(*) FROM memories WHERE project != '' GROUP BY project ORDER BY COUNT(*) DESC"
        ).fetchall())
        avg_importance = self.conn.execute(
            "SELECT AVG(importance) FROM memories"
        ).fetchone()[0] or 0

        return {
            "total": total,
            "by_type": by_type,
            "by_project": by_project,
            "avg_importance": round(avg_importance, 3),
            "db_size_kb": round(self.db_path.stat().st_size / 1024, 1) if self.db_path.exists() else 0,
        }

    def close(self):
        self.conn.close()


# ─── CLI ───

if __name__ == "__main__":
    import sys

    db = MemoryDB()

    if len(sys.argv) < 2:
        print("用法:")
        print("  python memory_db.py stats")
        print("  python memory_db.py search <query>")
        print("  python memory_db.py search <query> --project <project>")
        print("  python memory_db.py recall --project <project>")
        print("  python memory_db.py decay")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "stats":
        s = db.stats()
        print(json.dumps(s, ensure_ascii=False, indent=2))

    elif cmd == "search":
        query = sys.argv[2] if len(sys.argv) > 2 else ""
        project = ""
        if "--project" in sys.argv:
            idx = sys.argv.index("--project")
            project = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else ""

        results = db.search(query, project=project)
        for r in results:
            print(f"[{r['type']}] ({r['project']}/{r['agent']}) importance={r['importance']}")
            print(f"  {r['content'][:120]}")
            print()

    elif cmd == "recall":
        project = ""
        agent = ""
        if "--project" in sys.argv:
            idx = sys.argv.index("--project")
            project = sys.argv[idx + 1]
        if "--agent" in sys.argv:
            idx = sys.argv.index("--agent")
            agent = sys.argv[idx + 1]

        results = db.recall(project=project, agent=agent)
        text = db.format_for_injection(results)
        print(text)

    elif cmd == "decay":
        updated = db.decay_importance()
        print(f"Updated importance for {updated} memories")

    db.close()
