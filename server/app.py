"""
Agent Workforce — Server API

轻量 FastAPI 服务，部署在火山云 ECS (118.196.147.14)。

功能:
  1. 接收并存储 traces (POST /api/traces)
  2. 接收飞书按钮反馈 (GET /api/feedback?trace_id=xxx&rating=3)
  3. 查看 traces 列表 (GET /api/traces)
  4. 查看 agent 统计 (GET /api/stats)
  5. 简单 Web Dashboard (GET /)

运行:
  pip install fastapi uvicorn
  uvicorn app:app --host 0.0.0.0 --port 9100

端口: 9100 (不与现有服务冲突)
"""

import json
import os
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from contextlib import contextmanager

import sys
import asyncio
import uuid

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

# Memory DB (from scripts/)
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
try:
    from memory_db import MemoryDB
except ImportError:
    MemoryDB = None

app = FastAPI(title="Agent Workforce", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

CST = timezone(timedelta(hours=8))
DB_PATH = os.environ.get("AW_DB_PATH", "/data/agent-workforce/traces.db")


# =========================================================================
# Database
# =========================================================================

def init_db():
    """初始化 SQLite 数据库"""
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS traces (
                trace_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                project TEXT,
                scenario TEXT,
                agent_profile TEXT,
                goal TEXT,
                tool_call_count INTEGER DEFAULT 0,
                files_modified TEXT,  -- JSON array
                duration_sec REAL DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                estimated_cost_usd REAL DEFAULT 0,
                rounds INTEGER DEFAULT 0,
                build_success INTEGER,  -- NULL / 0 / 1
                human_feedback TEXT,  -- thumbs_up / thumbs_down / rework / golden
                failure_type TEXT,
                auto_score REAL,
                score_confidence TEXT,
                raw_data TEXT,  -- 完整 JSON
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_traces_date ON traces(timestamp)
        """)
        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_traces_agent ON traces(agent_profile)
        """)
        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_traces_project ON traces(project)
        """)

        # Skills 表
        db.execute("""
            CREATE TABLE IF NOT EXISTS skills (
                id TEXT PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                description TEXT DEFAULT '',
                content TEXT NOT NULL,
                projects TEXT DEFAULT '[]',
                agents TEXT DEFAULT '[]',
                triggers TEXT DEFAULT '[]',
                source_traces TEXT DEFAULT '[]',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                usage_count INTEGER DEFAULT 0
            )
        """)

        # Done Spec 字段 (v2)
        new_columns = [
            ("completion_score", "REAL"),
            ("quality_score", "REAL"),
            ("completion_status", "TEXT"),
            ("deliverables_met", "INTEGER"),
            ("verification_passed", "INTEGER"),
            ("scope_respected", "INTEGER"),
            ("session_tier", "TEXT"),
            ("summary", "TEXT"),
        ]
        for col_name, col_type in new_columns:
            try:
                db.execute(f"ALTER TABLE traces ADD COLUMN {col_name} {col_type}")
            except:
                pass  # 列已存在


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# =========================================================================
# API Routes
# =========================================================================

@app.on_event("startup")
async def startup():
    init_db()


@app.post("/api/traces")
async def create_trace(request: Request):
    """接收 trace 数据"""
    data = await request.json()
    trace_id = data.get("trace_id", "")
    if not trace_id:
        return JSONResponse({"error": "trace_id required"}, status_code=400)

    with get_db() as db:
        db.execute("""
            INSERT OR REPLACE INTO traces
            (trace_id, timestamp, project, scenario, agent_profile, goal,
             tool_call_count, files_modified, duration_sec, total_tokens,
             estimated_cost_usd, rounds, build_success, human_feedback,
             failure_type, auto_score, score_confidence, raw_data,
             completion_score, quality_score, completion_status,
             deliverables_met, verification_passed, scope_respected, session_tier, summary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trace_id,
            data.get("timestamp", ""),
            data.get("project", ""),
            data.get("scenario", ""),
            data.get("agent_profile", ""),
            data.get("goal", ""),
            data.get("tool_call_count", 0),
            json.dumps(data.get("files_modified", []), ensure_ascii=False),
            data.get("duration_sec", 0),
            data.get("total_tokens", 0),
            data.get("estimated_cost_usd", 0),
            data.get("rounds", 0),
            data.get("build_success"),
            data.get("human_feedback"),
            data.get("failure_type"),
            data.get("auto_score"),
            data.get("score_confidence"),
            json.dumps(data, ensure_ascii=False),
            data.get("completion_score"),
            data.get("quality_score"),
            data.get("completion_status"),
            data.get("deliverables_met"),
            data.get("verification_passed"),
            data.get("scope_respected"),
            data.get("session_tier"),
            data.get("summary"),
        ))

    return {"status": "ok", "trace_id": trace_id}


@app.get("/api/feedback")
async def receive_feedback(
    trace_id: str = Query(...),
    rating: str = Query(...),  # 1=thumbs_down, 2=rework, 3=thumbs_up, 4=golden
):
    """接收反馈 (飞书按钮 / 浏览器链接)"""
    rating_map = {
        "1": "thumbs_down", "thumbs_down": "thumbs_down",
        "2": "rework", "rework": "rework",
        "3": "thumbs_up", "thumbs_up": "thumbs_up",
        "4": "golden", "golden": "golden",
    }
    feedback = rating_map.get(rating, rating)

    with get_db() as db:
        result = db.execute(
            "UPDATE traces SET human_feedback = ? WHERE trace_id = ?",
            (feedback, trace_id)
        )
        if result.rowcount == 0:
            return JSONResponse({"error": "trace not found"}, status_code=404)

    emoji = {"thumbs_up": "👍", "thumbs_down": "👎", "rework": "🔄", "golden": "⭐"}.get(feedback, "?")

    # 如果是浏览器访问，返回一个简单的确认页
    return HTMLResponse(f"""
    <html><body style="display:flex;justify-content:center;align-items:center;height:100vh;
    font-family:-apple-system,sans-serif;font-size:48px;background:#f5f5f5;">
    <div style="text-align:center">
        <div>{emoji}</div>
        <div style="font-size:18px;color:#666;margin-top:16px">
            {trace_id} 已标记为 {feedback}
        </div>
    </div>
    </body></html>
    """)


@app.get("/api/traces")
async def list_traces(
    date: str = Query(None),
    agent: str = Query(None),
    project: str = Query(None),
    limit: int = Query(50),
):
    """查询 traces"""
    with get_db() as db:
        conditions = []
        params = []

        if date:
            conditions.append("timestamp LIKE ?")
            params.append(f"{date}%")
        if agent:
            conditions.append("agent_profile LIKE ?")
            params.append(f"%{agent}%")
        if project:
            conditions.append("project = ?")
            params.append(project)

        where = " AND ".join(conditions) if conditions else "1=1"
        rows = db.execute(
            f"SELECT * FROM traces WHERE {where} ORDER BY timestamp DESC LIMIT ?",
            params + [limit]
        ).fetchall()

    return [dict(r) for r in rows]


@app.get("/api/traces/{trace_id}")
async def get_trace_detail(trace_id: str):
    """获取单条 trace 完整详情"""
    with get_db() as db:
        row = db.execute("SELECT * FROM traces WHERE trace_id = ?", (trace_id,)).fetchone()
    if not row:
        return JSONResponse({"error": "trace not found"}, status_code=404)
    result = dict(row)
    raw = {}
    try:
        raw = json.loads(result.get("raw_data") or "{}")
    except:
        pass
    return {
        "trace_id": result["trace_id"],
        "timestamp": result["timestamp"],
        "project": result["project"],
        "scenario": result.get("scenario", ""),
        "agent": result["agent_profile"],
        "goal": result["goal"],
        "summary": result.get("summary") or raw.get("summary", ""),
        "duration_sec": result["duration_sec"],
        "rounds": result.get("rounds", 0),
        "auto_feedback": raw.get("auto_feedback"),
        "quality_score": result.get("quality_score"),
        "completion_score": result.get("completion_score"),
        "completion_status": result.get("completion_status", ""),
        "total_tokens": result["total_tokens"],
        "estimated_cost_usd": result["estimated_cost_usd"],
        "tokens_in": raw.get("tokens_in", 0),
        "tokens_out": raw.get("tokens_out", 0),
        "files_modified": raw.get("files_modified", []),
        "context_files_read": raw.get("context_files_read", []),
        "total_edits": raw.get("total_edits", 0),
        "retry_edits": raw.get("retry_edits", 0),
        "tool_calls": raw.get("tool_calls", []),
        "tool_call_count": result["tool_call_count"],
        "build_success": result["build_success"],
        "verification_passed": result.get("verification_passed"),
        "scope_respected": result.get("scope_respected"),
        "boundary_violations": raw.get("boundary_violations", []),
        "human_feedback": result["human_feedback"],
        "session_tier": result.get("session_tier", ""),
        "cwd": raw.get("cwd", ""),
    }


@app.get("/api/stats")
async def get_stats(days: int = Query(7)):
    """Agent 统计数据"""
    with get_db() as db:
        cutoff = (datetime.now(CST) - timedelta(days=days)).isoformat()

        rows = db.execute("""
            SELECT
                agent_profile,
                COUNT(*) as total_tasks,
                AVG(CASE WHEN auto_score IS NOT NULL THEN auto_score END) as avg_score,
                SUM(CASE WHEN human_feedback = 'thumbs_up' OR human_feedback = 'golden' THEN 1 ELSE 0 END) as positive,
                SUM(CASE WHEN human_feedback = 'thumbs_down' THEN 1 ELSE 0 END) as negative,
                SUM(estimated_cost_usd) as total_cost,
                AVG(duration_sec) as avg_duration
            FROM traces
            WHERE timestamp > ?
            GROUP BY agent_profile
            ORDER BY total_tasks DESC
        """, (cutoff,)).fetchall()

    return [dict(r) for r in rows]


PROFILES_DIR = os.environ.get("AW_PROFILES_DIR", "/opt/agent-workforce/profiles")


@app.get("/api/profiles")
async def list_profiles():
    """列出所有 Agent Profile"""
    profiles = []
    profiles_path = Path(PROFILES_DIR)
    if not profiles_path.exists():
        return []

    for agent_dir in sorted(profiles_path.iterdir()):
        if not agent_dir.is_dir():
            continue
        yamls = sorted(agent_dir.glob("v*.yaml"), reverse=True)
        if not yamls:
            continue

        # 读取最新 profile
        try:
            import yaml
            with open(yamls[0]) as f:
                profile = yaml.safe_load(f)
        except Exception:
            # 没有 pyyaml 时用简单解析
            text = yamls[0].read_text()
            profile = {"name": agent_dir.name, "raw": text}

        profile["_dir"] = agent_dir.name
        profile["_version"] = yamls[0].stem
        profile["_versions"] = [y.stem for y in yamls]
        golden_dir = agent_dir / "golden_examples"
        profile["_golden_count"] = len(list(golden_dir.glob("*.json"))) if golden_dir.exists() else 0
        profiles.append(profile)

    return profiles


@app.get("/profiles", response_class=HTMLResponse)
async def profiles_page():
    """Agent Profiles 页面"""
    profiles_path = Path(PROFILES_DIR)
    cards_html = ""

    if profiles_path.exists():
        for agent_dir in sorted(profiles_path.iterdir()):
            if not agent_dir.is_dir():
                continue
            yamls = sorted(agent_dir.glob("v*.yaml"), reverse=True)
            if not yamls:
                continue

            # 简单解析 YAML (不依赖 pyyaml)
            text = yamls[0].read_text()
            name = agent_dir.name
            model = ""
            version = yamls[0].stem
            role_lines = []
            can_do = []
            cannot_do = []

            in_role = False
            in_can = False
            in_cannot = False
            in_lessons = False
            lessons = []
            for line in text.split("\n"):
                stripped = line.strip()
                if stripped.startswith("name:"):
                    name = stripped.split(":", 1)[1].strip().strip('"')
                elif stripped.startswith("model:"):
                    model = stripped.split(":", 1)[1].strip().strip('"')
                elif stripped.startswith("role:"):
                    in_role = True; in_can = False; in_cannot = False; in_lessons = False
                elif stripped.startswith("can_do:"):
                    in_can = True; in_role = False; in_cannot = False; in_lessons = False
                elif stripped.startswith("cannot_do:"):
                    in_cannot = True; in_role = False; in_can = False; in_lessons = False
                elif stripped.startswith("lessons:"):
                    in_lessons = True; in_role = False; in_can = False; in_cannot = False
                elif stripped.startswith(("quality_gates:", "review_dimensions:", "workflow:", "projects:", "done_spec_fields:", "failure_definitions:", "deployment_knowledge:", "capabilities:", "human_approval_required:")):
                    in_role = False; in_can = False; in_cannot = False; in_lessons = False
                elif in_role and not stripped.startswith("- ") and stripped and not stripped.startswith("#"):
                    role_lines.append(stripped)
                elif in_can and stripped.startswith("- "):
                    can_do.append(stripped[2:].strip().strip('"'))
                elif in_cannot and stripped.startswith("- "):
                    cannot_do.append(stripped[2:].strip().strip('"'))
                elif in_lessons and stripped.startswith("lesson:"):
                    lesson_text = stripped.split(":", 1)[1].strip().strip('"')
                    if lesson_text:
                        lessons.append(lesson_text)

            role_text = " ".join(role_lines)[:200]
            golden_dir = agent_dir / "golden_examples"
            golden_count = len(list(golden_dir.glob("*.json"))) if golden_dir.exists() else 0

            model_color = {"opus": "#7c3aed", "sonnet": "#2563eb", "haiku": "#059669"}.get(model, "#666")

            can_html = "".join(f"<li>{c}</li>" for c in can_do[:5])
            cannot_html = "".join(f"<li>{c}</li>" for c in cannot_do[:5])
            lessons_html = "".join(f"<li>{l[:80]}</li>" for l in lessons[:6])
            lessons_section = f"""
                <div class="lessons-section">
                    <div class="col-title">Lessons ({len(lessons)})</div>
                    <ul class="lessons">{lessons_html}</ul>
                </div>
            """ if lessons else ""

            cards_html += f"""
            <div class="card">
                <div class="card-header">
                    <div>
                        <div class="agent-name">{name}</div>
                        <span class="model-badge" style="background:{model_color}">{model}</span>
                        <span class="version-badge">{version}</span>
                        <span class="golden-badge">{golden_count} golden</span>
                        <span class="lessons-badge">{len(lessons)} lessons</span>
                    </div>
                </div>
                <div class="role">{role_text}</div>
                <div class="columns">
                    <div>
                        <div class="col-title">Can do</div>
                        <ul>{can_html}</ul>
                    </div>
                    <div>
                        <div class="col-title">Cannot do</div>
                        <ul class="cannot">{cannot_html}</ul>
                    </div>
                </div>
                {lessons_section}
            </div>
            """

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Agent Profiles</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * {{ margin:0; padding:0; box-sizing:border-box; }}
            body {{ font-family:-apple-system,BlinkMacSystemFont,sans-serif; background:#f5f5f7; color:#1d1d1f; padding:20px; }}
            h1 {{ font-size:28px; margin-bottom:8px; }}
            .nav {{ margin-bottom:24px; font-size:14px; color:#86868b; }}
            .nav a {{ color:#0071e3; text-decoration:none; }}
            .cards {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(380px, 1fr)); gap:16px; }}
            .card {{ background:white; border-radius:12px; padding:20px; box-shadow:0 1px 3px rgba(0,0,0,0.1); }}
            .card-header {{ display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:12px; }}
            .agent-name {{ font-size:18px; font-weight:700; margin-bottom:6px; }}
            .model-badge {{ color:white; padding:2px 8px; border-radius:4px; font-size:12px; font-weight:600; }}
            .version-badge {{ background:#f0f0f0; padding:2px 8px; border-radius:4px; font-size:12px; margin-left:4px; }}
            .golden-badge {{ background:#fef3c7; color:#92400e; padding:2px 8px; border-radius:4px; font-size:12px; margin-left:4px; }}
            .role {{ font-size:13px; color:#86868b; margin-bottom:12px; line-height:1.4; }}
            .columns {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; }}
            .col-title {{ font-size:12px; font-weight:600; color:#86868b; margin-bottom:6px; text-transform:uppercase; }}
            ul {{ font-size:13px; padding-left:16px; }}
            li {{ margin-bottom:3px; }}
            .cannot li {{ color:#dc2626; }}
            .lessons-section {{ margin-top:12px; padding-top:12px; border-top:1px solid #f0f0f0; }}
            .lessons li {{ color:#0369a1; font-style:italic; }}
            .lessons-badge {{ background:#dbeafe; color:#1e40af; padding:2px 8px; border-radius:4px; font-size:12px; margin-left:4px; }}
        </style>
    </head>
    <body>
        <h1>Agent Profiles</h1>
        <div class="nav"><a href="./">Dashboard</a> / Profiles</div>
        <div class="cards">
            {cards_html}
        </div>
    </body>
    </html>
    """


# =========================================================================
# Web Dashboard
# =========================================================================

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """简单 Dashboard"""
    with get_db() as db:
        today = datetime.now(CST).strftime("%Y-%m-%d")

        # 今日统计
        today_stats = db.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN human_feedback IN ('thumbs_up','golden') THEN 1 ELSE 0 END) as positive,
                   SUM(CASE WHEN human_feedback = 'thumbs_down' THEN 1 ELSE 0 END) as negative,
                   SUM(estimated_cost_usd) as cost
            FROM traces WHERE timestamp LIKE ?
        """, (f"{today}%",)).fetchone()

        # 最近 traces
        recent = db.execute("""
            SELECT trace_id, timestamp, project, agent_profile, goal,
                   duration_sec, human_feedback, auto_score, raw_data
            FROM traces
            WHERE session_tier IS NULL
               OR session_tier IN ('significant', 'critical')
            ORDER BY timestamp DESC LIMIT 20
        """).fetchall()

        # Agent 统计 (7天)
        cutoff = (datetime.now(CST) - timedelta(days=7)).isoformat()
        agents = db.execute("""
            SELECT agent_profile, COUNT(*) as tasks,
                   AVG(auto_score) as avg_score,
                   SUM(estimated_cost_usd) as cost
            FROM traces WHERE timestamp > ?
            GROUP BY agent_profile ORDER BY tasks DESC
        """, (cutoff,)).fetchall()

    feedback_emoji = {
        "thumbs_up": "👍", "thumbs_down": "👎",
        "rework": "🔄", "golden": "⭐", None: "—"
    }

    traces_html = ""
    for r in recent:
        fb = feedback_emoji.get(r["human_feedback"], "—")
        # 优先显示 summary (agent 做了什么)，fallback 到 goal (用户说了什么)
        raw_data = {}
        try:
            raw_data = json.loads(r.get("raw_data") or "{}")
        except:
            pass
        summary = raw_data.get("summary", "")
        goal_text = (r["goal"] or "")[:60]
        # 过滤无意义的 goal (太短或是纯对话)
        if not summary and len(goal_text) <= 5:
            display_goal = f'<span style="color:#86868b">{goal_text or "—"}</span>'
        elif summary:
            display_goal = summary[:70]
        else:
            display_goal = goal_text
        dur = f"{r['duration_sec']:.0f}s" if r["duration_sec"] else "—"
        traces_html += f"""
        <tr>
            <td><code>{r['trace_id']}</code></td>
            <td>{r['project'] or '—'}</td>
            <td>{display_goal}</td>
            <td>{r['agent_profile'] or '—'}</td>
            <td>{dur}</td>
            <td style="font-size:20px">{fb}</td>
            <td>
                <a href="api/feedback?trace_id={r['trace_id']}&rating=3">👍</a>
                <a href="api/feedback?trace_id={r['trace_id']}&rating=2">🔄</a>
                <a href="api/feedback?trace_id={r['trace_id']}&rating=1">👎</a>
                <a href="api/feedback?trace_id={r['trace_id']}&rating=4">⭐</a>
            </td>
        </tr>"""

    agents_html = ""
    for a in agents:
        score = f"{a['avg_score']:.2f}" if a["avg_score"] else "—"
        agents_html += f"""
        <tr>
            <td>{a['agent_profile']}</td>
            <td>{a['tasks']}</td>
            <td>{score}</td>
            <td>${a['cost'] or 0:.2f}</td>
        </tr>"""

    total = today_stats["total"] or 0
    positive = today_stats["positive"] or 0
    negative = today_stats["negative"] or 0
    cost = today_stats["cost"] or 0

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Agent Workforce</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * {{ margin:0; padding:0; box-sizing:border-box; }}
            body {{ font-family:-apple-system,BlinkMacSystemFont,sans-serif; background:#f5f5f7; color:#1d1d1f; padding:20px; }}
            h1 {{ font-size:28px; margin-bottom:24px; }}
            .stats {{ display:flex; gap:16px; margin-bottom:24px; flex-wrap:wrap; }}
            .stat {{ background:white; border-radius:12px; padding:20px; flex:1; min-width:120px; box-shadow:0 1px 3px rgba(0,0,0,0.1); }}
            .stat .value {{ font-size:32px; font-weight:700; }}
            .stat .label {{ font-size:13px; color:#86868b; margin-top:4px; }}
            table {{ width:100%; border-collapse:collapse; background:white; border-radius:12px; overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,0.1); margin-bottom:24px; }}
            th {{ text-align:left; padding:12px 16px; background:#f5f5f7; font-size:13px; color:#86868b; font-weight:600; }}
            td {{ padding:10px 16px; border-top:1px solid #f0f0f0; font-size:14px; }}
            code {{ background:#f0f0f0; padding:2px 6px; border-radius:4px; font-size:12px; }}
            a {{ color:#0071e3; text-decoration:none; margin:0 4px; font-size:18px; }}
            a:hover {{ opacity:0.7; }}
            h2 {{ font-size:20px; margin:24px 0 12px; }}
        </style>
    </head>
    <body>
        <h1>Agent Workforce</h1>

        <div class="stats">
            <div class="stat"><div class="value">{total}</div><div class="label">Today Tasks</div></div>
            <div class="stat"><div class="value">{positive}</div><div class="label">👍 Positive</div></div>
            <div class="stat"><div class="value">{negative}</div><div class="label">👎 Negative</div></div>
            <div class="stat"><div class="value">${cost:.2f}</div><div class="label">Cost</div></div>
        </div>

        <h2>Agent Performance (7 days)  <a href="profiles" style="font-size:14px;font-weight:400">View Profiles →</a></h2>
        <table>
            <tr><th>Agent</th><th>Tasks</th><th>Avg Score</th><th>Cost</th></tr>
            {agents_html}
        </table>

        <h2>Recent Traces</h2>
        <table>
            <tr><th>Trace</th><th>Project</th><th>Summary</th><th>Agent</th><th>Duration</th><th>Feedback</th><th>Rate</th></tr>
            {traces_html}
        </table>
    </body>
    </html>
    """


# =========================================================================
# Skills CRUD API
# =========================================================================

@app.post("/api/skills")
async def create_skill(request: Request):
    """创建 Skill"""
    data = await request.json()
    name = data.get("name", "").strip()
    content = data.get("content", "").strip()
    if not name or not content:
        return JSONResponse({"error": "name and content required"}, status_code=400)

    skill_id = data.get("id") or f"skill_{uuid.uuid4().hex[:8]}"
    now = datetime.now(CST).isoformat()

    with get_db() as db:
        try:
            db.execute("""
                INSERT INTO skills (id, name, description, content, projects, agents,
                    triggers, source_traces, created_at, updated_at, usage_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (
                skill_id, name,
                data.get("description", ""),
                content,
                json.dumps(data.get("projects", []), ensure_ascii=False),
                json.dumps(data.get("agents", []), ensure_ascii=False),
                json.dumps(data.get("triggers", []), ensure_ascii=False),
                json.dumps(data.get("source_traces", []), ensure_ascii=False),
                now, now,
            ))
        except sqlite3.IntegrityError:
            return JSONResponse({"error": f"skill name '{name}' already exists"}, status_code=409)

    return {"status": "ok", "id": skill_id}


@app.get("/api/skills")
async def list_skills(
    project: str = Query(None),
    agent: str = Query(None),
    limit: int = Query(100),
):
    """列出 Skills，支持 project/agent 筛选"""
    with get_db() as db:
        conditions = []
        params = []

        if project:
            # JSON array 里包含该 project
            conditions.append("projects LIKE ?")
            params.append(f'%"{project}"%')
        if agent:
            conditions.append("agents LIKE ?")
            params.append(f'%"{agent}"%')

        where = " AND ".join(conditions) if conditions else "1=1"
        rows = db.execute(
            f"SELECT * FROM skills WHERE {where} ORDER BY updated_at DESC LIMIT ?",
            params + [limit]
        ).fetchall()

    results = []
    for r in rows:
        d = dict(r)
        # 解析 JSON 字段
        for field in ("projects", "agents", "triggers", "source_traces"):
            try:
                d[field] = json.loads(d[field])
            except (json.JSONDecodeError, TypeError):
                d[field] = []
        results.append(d)

    return results


@app.get("/api/skills/{skill_id}")
async def get_skill(skill_id: str):
    """获取 Skill 详情"""
    with get_db() as db:
        row = db.execute("SELECT * FROM skills WHERE id = ?", (skill_id,)).fetchone()
    if not row:
        return JSONResponse({"error": "skill not found"}, status_code=404)

    d = dict(row)
    for field in ("projects", "agents", "triggers", "source_traces"):
        try:
            d[field] = json.loads(d[field])
        except (json.JSONDecodeError, TypeError):
            d[field] = []
    return d


@app.put("/api/skills/{skill_id}")
async def update_skill(skill_id: str, request: Request):
    """更新 Skill"""
    data = await request.json()
    now = datetime.now(CST).isoformat()

    with get_db() as db:
        existing = db.execute("SELECT id FROM skills WHERE id = ?", (skill_id,)).fetchone()
        if not existing:
            return JSONResponse({"error": "skill not found"}, status_code=404)

        updates = []
        params = []
        for field in ("name", "description", "content"):
            if field in data:
                updates.append(f"{field} = ?")
                params.append(data[field])
        for field in ("projects", "agents", "triggers", "source_traces"):
            if field in data:
                updates.append(f"{field} = ?")
                params.append(json.dumps(data[field], ensure_ascii=False))
        if "usage_count" in data:
            updates.append("usage_count = ?")
            params.append(data["usage_count"])

        updates.append("updated_at = ?")
        params.append(now)
        params.append(skill_id)

        db.execute(f"UPDATE skills SET {', '.join(updates)} WHERE id = ?", params)

    return {"status": "ok", "id": skill_id}


@app.delete("/api/skills/{skill_id}")
async def delete_skill(skill_id: str):
    """删除 Skill"""
    with get_db() as db:
        result = db.execute("DELETE FROM skills WHERE id = ?", (skill_id,))
        if result.rowcount == 0:
            return JSONResponse({"error": "skill not found"}, status_code=404)
    return {"status": "ok", "id": skill_id}


# =========================================================================
# Activity Feed API
# =========================================================================

@app.get("/api/activity")
async def activity_feed(
    date: str = Query(None),
    project: str = Query(None),
    agent: str = Query(None),
    limit: int = Query(50),
):
    """统一时间线 Activity Feed，从 traces 提取结构化摘要"""
    with get_db() as db:
        conditions = []
        params = []

        if date:
            conditions.append("timestamp LIKE ?")
            params.append(f"{date}%")
        if project:
            conditions.append("project = ?")
            params.append(project)
        if agent:
            conditions.append("agent_profile LIKE ?")
            params.append(f"%{agent}%")

        where = " AND ".join(conditions) if conditions else "1=1"
        rows = db.execute(
            f"""SELECT trace_id, timestamp, project, agent_profile,
                       goal, summary, duration_sec, auto_score, quality_score,
                       files_modified, raw_data, human_feedback
                FROM traces WHERE {where}
                ORDER BY timestamp DESC LIMIT ?""",
            params + [limit]
        ).fetchall()

    activities = []
    for r in rows:
        raw = {}
        try:
            raw = json.loads(r["raw_data"] or "{}")
        except (json.JSONDecodeError, TypeError):
            pass

        # 提取 summary: 优先 DB 列 → raw_data → goal
        summary = r["summary"] or raw.get("summary", "") or (r["goal"] or "")[:100]

        # 提取 files_modified
        files_modified = []
        try:
            files_modified = json.loads(r["files_modified"] or "[]")
        except (json.JSONDecodeError, TypeError):
            pass

        # auto_feedback: 从 human_feedback 映射数值
        feedback_score_map = {
            "thumbs_down": 1, "rework": 2, "thumbs_up": 3, "golden": 4,
        }
        auto_feedback = feedback_score_map.get(r["human_feedback"])

        activities.append({
            "type": "trace",
            "trace_id": r["trace_id"],
            "timestamp": r["timestamp"],
            "project": r["project"] or "",
            "agent": r["agent_profile"] or "",
            "summary": summary,
            "auto_feedback": auto_feedback,
            "quality_score": r["quality_score"] or raw.get("quality_score"),
            "files_modified": files_modified,
            "duration_sec": r["duration_sec"],
        })

    return activities


@app.get("/api/activity/grouped")
async def activity_feed_grouped(
    date: str = Query(None),
    project: str = Query(None),
    agent: str = Query(None),
    limit: int = Query(80),
    gap_minutes: int = Query(30),
):
    """Session 聚合的 Activity Feed: 同 project + 30分钟内的 traces 合为一组"""
    # 先获取原始 activity
    activities = await activity_feed(date=date, project=project, agent=agent, limit=limit)

    if not activities:
        return []

    # 按时间 + 项目分组
    sessions = []
    current = None

    for item in activities:
        ts_str = (item.get("timestamp") or "")[:19]
        proj = item.get("project", "")
        try:
            from datetime import datetime as dt
            ts = dt.fromisoformat(ts_str)
        except Exception:
            ts = None

        should_merge = (
            current is not None
            and proj == current["project"]
            and ts is not None
            and current["_last_ts"] is not None
            and abs((current["_last_ts"] - ts).total_seconds()) < gap_minutes * 60
        )

        if should_merge:
            current["traces"].append(item)
            current["_last_ts"] = ts
            current["trace_count"] = len(current["traces"])
            current["total_duration"] += item.get("duration_sec") or 0
            fm = item.get("files_modified") or []
            current["all_files"].extend(fm)
        else:
            if current:
                current.pop("_last_ts", None)
                current["all_files"] = list(set(current["all_files"]))
                sessions.append(current)

            current = {
                "session_id": item.get("trace_id", ""),
                "project": proj,
                "agent": item.get("agent", ""),
                "timestamp": item.get("timestamp", ""),
                "trace_count": 1,
                "total_duration": item.get("duration_sec") or 0,
                "all_files": list(item.get("files_modified") or []),
                "summary": item.get("summary", ""),
                "auto_feedback": item.get("auto_feedback"),
                "quality_score": item.get("quality_score"),
                "traces": [item],
                "_last_ts": ts,
            }

    if current:
        current.pop("_last_ts", None)
        current["all_files"] = list(set(current["all_files"]))
        sessions.append(current)

    return sessions


# =========================================================================
# Memory API
# =========================================================================

def _get_memory_db():
    """获取 MemoryDB 实例，自动检测路径"""
    if MemoryDB is None:
        return None
    # 本地: ~/agent-workforce/knowledge/memory.db
    # 服务器: /opt/agent-workforce/knowledge/memory.db
    local_path = Path.home() / "agent-workforce" / "knowledge" / "memory.db"
    server_path = Path("/opt/agent-workforce/knowledge/memory.db")
    db_path = local_path if local_path.exists() else server_path
    return MemoryDB(db_path)


@app.get("/api/memory/search")
async def memory_search(
    q: str = Query(..., description="搜索关键词"),
    project: str = Query(""),
    agent: str = Query(""),
    limit: int = Query(10),
):
    """全文搜索记忆库"""
    mdb = _get_memory_db()
    if mdb is None:
        return JSONResponse({"error": "MemoryDB not available"}, status_code=503)
    try:
        results = mdb.search(q, project=project, agent=agent, limit=limit)
        return results
    finally:
        mdb.close()


@app.get("/api/memory/recall")
async def memory_recall(
    project: str = Query(""),
    agent: str = Query(""),
    limit: int = Query(5),
):
    """按 project/agent 召回高重要性记忆"""
    mdb = _get_memory_db()
    if mdb is None:
        return JSONResponse({"error": "MemoryDB not available"}, status_code=503)
    try:
        results = mdb.recall(project=project, agent=agent, limit=limit)
        return results
    finally:
        mdb.close()


@app.get("/api/memory/stats")
async def memory_stats():
    """记忆库统计"""
    mdb = _get_memory_db()
    if mdb is None:
        return JSONResponse({"error": "MemoryDB not available"}, status_code=503)
    try:
        return mdb.stats()
    finally:
        mdb.close()


# =========================================================================
# Agent 增强 API
# =========================================================================

@app.get("/api/agents")
async def list_agents(days: int = Query(30)):
    """
    列出所有 Agent，包含:
    - 从 traces GROUP BY 统计 (任务数、平均分、成本等)
    - 从 profiles 目录读取 YAML 元信息
    """
    with get_db() as db:
        cutoff = (datetime.now(CST) - timedelta(days=days)).isoformat()
        rows = db.execute("""
            SELECT
                agent_profile,
                COUNT(*) as total_tasks,
                AVG(auto_score) as avg_score,
                AVG(quality_score) as avg_quality,
                SUM(CASE WHEN human_feedback IN ('thumbs_up','golden') THEN 1 ELSE 0 END) as positive,
                SUM(CASE WHEN human_feedback = 'thumbs_down' THEN 1 ELSE 0 END) as negative,
                SUM(estimated_cost_usd) as total_cost,
                AVG(duration_sec) as avg_duration,
                MAX(timestamp) as last_active
            FROM traces
            WHERE timestamp > ?
              AND agent_profile NOT IN ('unknown_v1.0', '')
              AND agent_profile IS NOT NULL
            GROUP BY agent_profile
            ORDER BY total_tasks DESC
        """, (cutoff,)).fetchall()

    # 读取 profile YAML 元信息
    profiles_meta = {}
    profiles_path = Path(PROFILES_DIR)
    if profiles_path.exists():
        for agent_dir in profiles_path.iterdir():
            if not agent_dir.is_dir():
                continue
            yamls = sorted(agent_dir.glob("v*.yaml"), reverse=True)
            if not yamls:
                continue
            meta = {"dir": agent_dir.name, "version": yamls[0].stem}
            # 简单解析 name/model
            try:
                text = yamls[0].read_text()
                for line in text.split("\n"):
                    stripped = line.strip()
                    if stripped.startswith("name:"):
                        meta["name"] = stripped.split(":", 1)[1].strip().strip('"')
                    elif stripped.startswith("model:"):
                        meta["model"] = stripped.split(":", 1)[1].strip().strip('"')
            except Exception:
                pass
            profiles_meta[agent_dir.name] = meta

    agents = []
    for r in rows:
        agent_id = r["agent_profile"] or "unknown"
        d = dict(r)
        # 匹配 profile 目录名 (agent_profile 可能包含版本号如 netops_agent_v1.0)
        matched_profile = {}
        for dirname, meta in profiles_meta.items():
            if dirname in agent_id or agent_id in dirname:
                matched_profile = meta
                break
        d["profile"] = matched_profile
        agents.append(d)

    return agents


@app.get("/api/agents/{agent_id}")
async def get_agent_detail(agent_id: str, days: int = Query(30)):
    """
    Agent 详情:
    - 统计数据
    - 绑定的 skills
    - 最近 10 条 trace
    - 热点文件 (最常修改的文件)
    """
    with get_db() as db:
        cutoff = (datetime.now(CST) - timedelta(days=days)).isoformat()

        # 统计
        stats = db.execute("""
            SELECT
                COUNT(*) as total_tasks,
                AVG(auto_score) as avg_score,
                AVG(quality_score) as avg_quality,
                SUM(CASE WHEN human_feedback IN ('thumbs_up','golden') THEN 1 ELSE 0 END) as positive,
                SUM(CASE WHEN human_feedback = 'thumbs_down' THEN 1 ELSE 0 END) as negative,
                SUM(estimated_cost_usd) as total_cost,
                AVG(duration_sec) as avg_duration,
                MAX(timestamp) as last_active,
                MIN(timestamp) as first_seen
            FROM traces
            WHERE agent_profile LIKE ? AND timestamp > ?
        """, (f"%{agent_id}%", cutoff)).fetchone()

        if not stats or stats["total_tasks"] == 0:
            return JSONResponse({"error": "agent not found or no traces"}, status_code=404)

        # 最近 10 条 trace
        recent_traces = db.execute("""
            SELECT trace_id, timestamp, project, goal, summary,
                   duration_sec, auto_score, quality_score, human_feedback, files_modified
            FROM traces
            WHERE agent_profile LIKE ?
            ORDER BY timestamp DESC LIMIT 10
        """, (f"%{agent_id}%",)).fetchall()

        # 热点文件: 统计所有 files_modified
        all_files_rows = db.execute("""
            SELECT files_modified FROM traces
            WHERE agent_profile LIKE ? AND timestamp > ?
        """, (f"%{agent_id}%", cutoff)).fetchall()

    # 计算热点文件
    file_counts = {}
    for row in all_files_rows:
        try:
            files = json.loads(row["files_modified"] or "[]")
            for f in files:
                fname = f if isinstance(f, str) else str(f)
                file_counts[fname] = file_counts.get(fname, 0) + 1
        except (json.JSONDecodeError, TypeError):
            pass

    hot_files = sorted(file_counts.items(), key=lambda x: -x[1])[:20]

    # 绑定的 skills
    bound_skills = []
    with get_db() as db:
        skill_rows = db.execute(
            "SELECT id, name, description, usage_count FROM skills WHERE agents LIKE ?",
            (f'%"{agent_id}"%',)
        ).fetchall()
        bound_skills = [dict(s) for s in skill_rows]

    return {
        "agent_id": agent_id,
        "stats": dict(stats),
        "recent_traces": [dict(r) for r in recent_traces],
        "hot_files": [{"file": f, "count": c} for f, c in hot_files],
        "skills": bound_skills,
    }


# =========================================================================
# SSE 实时推送
# =========================================================================

@app.get("/sse")
async def sse_stream():
    """Server-Sent Events 端点，推送新 trace 通知"""
    async def generate():
        last_count = 0
        while True:
            try:
                with get_db() as db:
                    current_count = db.execute("SELECT COUNT(*) FROM traces").fetchone()[0]
                if current_count > last_count:
                    last_count = current_count
                    data = json.dumps({"type": "trace:new", "count": current_count}, ensure_ascii=False)
                    yield f"data: {data}\n\n"
                elif last_count == 0:
                    # 首次连接发送当前状态
                    last_count = current_count
                    data = json.dumps({"type": "connected", "count": current_count}, ensure_ascii=False)
                    yield f"data: {data}\n\n"
            except Exception:
                pass
            await asyncio.sleep(3)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9100)
