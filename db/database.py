"""
SQLite database for Reddit Demand Radar.
Database path is always relative to the project root, not cwd.
"""

import os
import sqlite3
import json
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from settings import get_config_value, resolve_project_path

# .env lives in project root, which is the parent of db/
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

DB_PATH = resolve_project_path(
    get_config_value("database.path", "data/radar.db"),
    "data/radar.db",
)

POST_SCHEMA_ADDITIONS = {
    "beginner_difficulty": "INTEGER",
    "free_build_possible": "TEXT",
    "beginner_reason": "TEXT",
}


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _ensure_post_columns(conn):
    existing = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(posts)").fetchall()
    }
    for column, column_type in POST_SCHEMA_ADDITIONS.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE posts ADD COLUMN {column} {column_type}")
    conn.commit()


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reddit_id TEXT UNIQUE NOT NULL,
            title TEXT,
            body TEXT,
            url TEXT,
            subreddit TEXT,
            score INTEGER DEFAULT 0,
            num_comments INTEGER DEFAULT 0,
            created_utc REAL,
            scraped_at TEXT,
            filter_score REAL,
            one_line_summary TEXT,
            analysis_status TEXT DEFAULT 'new',
            error_message TEXT,
            retry_count INTEGER DEFAULT 0,
            raw_filter_json TEXT,
            pain_point TEXT,
            user_quote TEXT,
            target_audience TEXT,
            project_idea TEXT,
            difficulty INTEGER,
            opensource_value TEXT,
            opensource_reason TEXT,
            monetize_potential TEXT,
            monetize_reason TEXT,
            beginner_difficulty INTEGER,
            free_build_possible TEXT,
            beginner_reason TEXT,
            confidence TEXT,
            insight_json TEXT
        )
    """)
    _ensure_post_columns(conn)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT UNIQUE NOT NULL,
            source TEXT NOT NULL,
            keyword TEXT,
            subreddit TEXT,
            limit_count INTEGER,
            status TEXT DEFAULT 'created',
            created_at TEXT,
            updated_at TEXT,
            started_at TEXT,
            completed_at TEXT,
            fetched_count INTEGER DEFAULT 0,
            new_count INTEGER DEFAULT 0,
            skipped_count INTEGER DEFAULT 0,
            filtered_out_count INTEGER DEFAULT 0,
            analyzed_count INTEGER DEFAULT 0,
            failed_count INTEGER DEFAULT 0,
            cancelled INTEGER DEFAULT 0,
            error_message TEXT,
            metadata_json TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS run_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            reddit_id TEXT NOT NULL,
            created_at TEXT,
            UNIQUE(run_id, reddit_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ai_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            call_id TEXT UNIQUE NOT NULL,
            run_id TEXT,
            reddit_id TEXT,
            stage TEXT,
            model TEXT,
            status TEXT,
            attempt_count INTEGER DEFAULT 1,
            prompt_chars INTEGER DEFAULT 0,
            response_chars INTEGER DEFAULT 0,
            started_at TEXT,
            completed_at TEXT,
            duration_ms INTEGER,
            error_message TEXT,
            raw_response TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS analysis_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            result_id TEXT UNIQUE NOT NULL,
            run_id TEXT,
            reddit_id TEXT NOT NULL,
            stage TEXT NOT NULL,
            score REAL,
            summary TEXT,
            created_at TEXT,
            result_json TEXT
        )
    """)
    conn.commit()
    conn.close()


def insert_post(post_dict):
    now = _utc_now()
    post_dict.setdefault("scraped_at", now)
    columns = ", ".join(post_dict.keys())
    placeholders = ", ".join(["?" for _ in post_dict])
    values = list(post_dict.values())
    conn = get_connection()
    conn.execute(
        f"INSERT OR IGNORE INTO posts ({columns}) VALUES ({placeholders})",
        values,
    )
    conn.commit()
    inserted = conn.total_changes > 0
    conn.close()
    return inserted


def create_run(
    source,
    keyword=None,
    subreddit=None,
    limit_count=None,
    status="created",
    metadata=None,
):
    run_id = str(uuid.uuid4())
    now = _utc_now()
    conn = get_connection()
    conn.execute(
        """INSERT INTO runs (
               run_id, source, keyword, subreddit, limit_count, status,
               created_at, updated_at, started_at, metadata_json
           )
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            run_id,
            source,
            keyword,
            subreddit,
            limit_count,
            status,
            now,
            now,
            now if status not in {"created", "ingested"} else None,
            json.dumps(metadata or {}, ensure_ascii=False),
        ),
    )
    conn.commit()
    conn.close()
    return run_id


def update_run(run_id, status=None, stats=None, error_message=None, metadata=None):
    if not run_id:
        return

    stats = stats or {}
    fields = ["updated_at = ?"]
    values = [_utc_now()]

    if status is not None:
        fields.append("status = ?")
        values.append(status)
        if status in {"scraping", "analyzing"}:
            fields.append("started_at = COALESCE(started_at, ?)")
            values.append(_utc_now())
        if status in {"completed", "cancelled", "failed"}:
            fields.append("completed_at = ?")
            values.append(_utc_now())
        if status == "cancelled":
            fields.append("cancelled = 1")

    mapping = {
        "fetched": "fetched_count",
        "new": "new_count",
        "skipped": "skipped_count",
        "filtered_out": "filtered_out_count",
        "analyzed": "analyzed_count",
        "failed": "failed_count",
    }
    for stat_key, column in mapping.items():
        if stat_key in stats:
            fields.append(f"{column} = ?")
            values.append(int(stats.get(stat_key) or 0))

    if stats.get("cancelled"):
        fields.append("cancelled = 1")

    if error_message:
        fields.append("error_message = ?")
        values.append(str(error_message)[:1000])

    if metadata is not None:
        fields.append("metadata_json = ?")
        values.append(json.dumps(metadata, ensure_ascii=False))

    values.append(run_id)
    conn = get_connection()
    conn.execute(f"UPDATE runs SET {', '.join(fields)} WHERE run_id = ?", values)
    conn.commit()
    conn.close()


def add_run_post(run_id, reddit_id):
    if not run_id or not reddit_id:
        return
    conn = get_connection()
    conn.execute(
        """INSERT OR IGNORE INTO run_posts (run_id, reddit_id, created_at)
           VALUES (?, ?, ?)""",
        (run_id, reddit_id, _utc_now()),
    )
    conn.commit()
    conn.close()


def add_run_posts(run_id, reddit_ids):
    for reddit_id in _normalize_reddit_ids(reddit_ids) or []:
        add_run_post(run_id, reddit_id)


def get_run_reddit_ids(run_id):
    conn = get_connection()
    rows = conn.execute(
        """SELECT reddit_id FROM run_posts
           WHERE run_id = ?
           ORDER BY id ASC""",
        (run_id,),
    ).fetchall()
    conn.close()
    return [row["reddit_id"] for row in rows]


def start_ai_call(run_id, reddit_id, stage, model, prompt_chars=0):
    call_id = str(uuid.uuid4())
    conn = get_connection()
    conn.execute(
        """INSERT INTO ai_calls (
               call_id, run_id, reddit_id, stage, model, status,
               prompt_chars, started_at
           )
           VALUES (?, ?, ?, ?, ?, 'started', ?, ?)""",
        (call_id, run_id, reddit_id, stage, model, int(prompt_chars or 0), _utc_now()),
    )
    conn.commit()
    conn.close()
    return call_id


def finish_ai_call(
    call_id,
    status,
    attempt_count=1,
    response_text=None,
    error_message=None,
    duration_ms=None,
):
    if not call_id:
        return
    conn = get_connection()
    conn.execute(
        """UPDATE ai_calls
           SET status = ?,
               attempt_count = ?,
               response_chars = ?,
               completed_at = ?,
               duration_ms = ?,
               error_message = ?,
               raw_response = ?
           WHERE call_id = ?""",
        (
            status,
            int(attempt_count or 1),
            len(response_text or ""),
            _utc_now(),
            duration_ms,
            str(error_message)[:1000] if error_message else None,
            response_text,
            call_id,
        ),
    )
    conn.commit()
    conn.close()


def record_analysis_result(run_id, reddit_id, stage, result_dict):
    if not reddit_id or not stage:
        return
    result_id = str(uuid.uuid4())
    score = result_dict.get("total") if isinstance(result_dict, dict) else None
    summary = result_dict.get("one_line_summary") if isinstance(result_dict, dict) else None
    conn = get_connection()
    conn.execute(
        """INSERT INTO analysis_results (
               result_id, run_id, reddit_id, stage, score, summary,
               created_at, result_json
           )
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            result_id,
            run_id,
            reddit_id,
            stage,
            score,
            summary,
            _utc_now(),
            json.dumps(result_dict or {}, ensure_ascii=False),
        ),
    )
    conn.commit()
    conn.close()


def _normalize_reddit_ids(reddit_ids):
    if reddit_ids is None:
        return None
    return list(dict.fromkeys(str(reddit_id) for reddit_id in reddit_ids if reddit_id))


def get_unprocessed_posts(limit=None, reddit_ids=None):
    normalized_ids = _normalize_reddit_ids(reddit_ids)
    if normalized_ids == []:
        return []

    conn = get_connection()
    params = []
    query = "SELECT * FROM posts WHERE analysis_status = 'new'"
    if normalized_ids is not None:
        placeholders = ",".join(["?"] * len(normalized_ids))
        query += f" AND reddit_id IN ({placeholders})"
        params.extend(normalized_ids)
    query += " ORDER BY score DESC"
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
    else:
        rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def update_filter_score(reddit_id, score, summary, raw_json=None):
    conn = get_connection()
    conn.execute(
        """UPDATE posts
           SET filter_score = ?,
               one_line_summary = ?,
               raw_filter_json = ?,
               analysis_status = 'filtered'
           WHERE reddit_id = ?""",
        (score, summary, raw_json, reddit_id),
    )
    conn.commit()
    conn.close()


def mark_filtered_out(reddit_id):
    conn = get_connection()
    conn.execute(
        "UPDATE posts SET analysis_status = 'filtered_out' WHERE reddit_id = ?",
        (reddit_id,),
    )
    conn.commit()
    conn.close()


def get_high_score_posts(threshold=5.0, reddit_ids=None):
    normalized_ids = _normalize_reddit_ids(reddit_ids)
    if normalized_ids == []:
        return []

    conn = get_connection()
    params = [threshold]
    ids_clause = ""
    if normalized_ids is not None:
        placeholders = ",".join(["?"] * len(normalized_ids))
        ids_clause = f" AND reddit_id IN ({placeholders})"
        params.extend(normalized_ids)
    rows = conn.execute(
        f"""SELECT * FROM posts
            WHERE analysis_status = 'filtered'
              AND filter_score >= ?
              {ids_clause}
            ORDER BY filter_score DESC""",
        params,
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def update_full_analysis(reddit_id, analysis_dict):
    conn = get_connection()
    _ensure_post_columns(conn)
    conn.execute(
        """UPDATE posts
           SET pain_point = ?,
               user_quote = ?,
               target_audience = ?,
               project_idea = ?,
               difficulty = ?,
               opensource_value = ?,
               opensource_reason = ?,
               monetize_potential = ?,
               monetize_reason = ?,
               beginner_difficulty = ?,
               free_build_possible = ?,
               beginner_reason = ?,
               confidence = ?,
               insight_json = ?,
               analysis_status = 'analyzed'
           WHERE reddit_id = ?""",
        (
            analysis_dict.get("pain_point"),
            analysis_dict.get("user_quote"),
            analysis_dict.get("target_audience"),
            analysis_dict.get("project_idea"),
            analysis_dict.get("difficulty"),
            analysis_dict.get("opensource_value"),
            analysis_dict.get("opensource_reason"),
            analysis_dict.get("monetize_potential"),
            analysis_dict.get("monetize_reason"),
            analysis_dict.get("beginner_difficulty"),
            analysis_dict.get("free_build_possible"),
            analysis_dict.get("beginner_reason"),
            analysis_dict.get("confidence"),
            json.dumps(analysis_dict, ensure_ascii=False),
            reddit_id,
        ),
    )
    conn.commit()
    conn.close()


def mark_post_failed(reddit_id, error_message):
    conn = get_connection()
    conn.execute(
        """UPDATE posts
           SET error_message = ?,
               retry_count = retry_count + 1,
               analysis_status = 'failed'
           WHERE reddit_id = ?""",
        (error_message, reddit_id),
    )
    conn.commit()
    conn.close()
