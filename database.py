"""
database.py — SQLite storage layer for the web crawler + search engine.
Manages pages, crawl queue, and crawl sessions with thread-safe access.
"""

import sqlite3
import os
import threading
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "crawler.db")

_local = threading.local()


def _get_conn():
    """Get a thread-local SQLite connection."""
    if not hasattr(_local, "conn") or _local.conn is None:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.row_factory = sqlite3.Row
        _local.conn = conn
    return _local.conn


def init_db():
    """Initialize database tables."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE NOT NULL,
            origin_url TEXT NOT NULL,
            depth INTEGER NOT NULL,
            title TEXT DEFAULT '',
            body_text TEXT DEFAULT '',
            crawled_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            origin_url TEXT NOT NULL,
            depth INTEGER NOT NULL,
            session_id INTEGER NOT NULL,
            status TEXT DEFAULT 'pending'
        );

        CREATE TABLE IF NOT EXISTS crawl_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            origin_url TEXT NOT NULL,
            max_depth INTEGER NOT NULL,
            status TEXT DEFAULT 'running',
            created_at TEXT NOT NULL,
            pages_crawled INTEGER DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_pages_url ON pages(url);
        CREATE INDEX IF NOT EXISTS idx_queue_status ON queue(status);
        CREATE INDEX IF NOT EXISTS idx_queue_session ON queue(session_id);
    """)
    conn.commit()


def create_session(origin_url, max_depth):
    """Create a new crawl session and return its ID."""
    conn = _get_conn()
    cursor = conn.execute(
        "INSERT INTO crawl_sessions (origin_url, max_depth, status, created_at) VALUES (?, ?, 'running', ?)",
        (origin_url, max_depth, datetime.utcnow().isoformat())
    )
    conn.commit()
    return cursor.lastrowid


def update_session_status(session_id, status):
    """Update crawl session status."""
    conn = _get_conn()
    conn.execute("UPDATE crawl_sessions SET status = ? WHERE id = ?", (status, session_id))
    conn.commit()


def increment_session_pages(session_id):
    """Increment the pages_crawled counter for a session."""
    conn = _get_conn()
    conn.execute("UPDATE crawl_sessions SET pages_crawled = pages_crawled + 1 WHERE id = ?", (session_id,))
    conn.commit()


def is_visited(url):
    """Check if a URL has already been crawled."""
    conn = _get_conn()
    row = conn.execute("SELECT 1 FROM pages WHERE url = ?", (url,)).fetchone()
    return row is not None


def save_page(url, origin_url, depth, title, body_text):
    """Save a crawled page. Returns True if inserted, False if duplicate."""
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO pages (url, origin_url, depth, title, body_text, crawled_at) VALUES (?, ?, ?, ?, ?, ?)",
            (url, origin_url, depth, title, body_text, datetime.utcnow().isoformat())
        )
        conn.commit()
        return conn.total_changes > 0
    except sqlite3.IntegrityError:
        return False


def add_to_queue(url, origin_url, depth, session_id):
    """Add a URL to the crawl queue."""
    conn = _get_conn()
    conn.execute(
        "INSERT INTO queue (url, origin_url, depth, session_id, status) VALUES (?, ?, ?, ?, 'pending')",
        (url, origin_url, depth, session_id)
    )
    conn.commit()


def add_to_queue_bulk(entries, session_id):
    """Add multiple URLs to the crawl queue.
    entries: list of (url, origin_url, depth) tuples.
    """
    conn = _get_conn()
    conn.executemany(
        "INSERT INTO queue (url, origin_url, depth, session_id, status) VALUES (?, ?, ?, ?, 'pending')",
        [(url, origin, depth, session_id) for url, origin, depth in entries]
    )
    conn.commit()


def pop_from_queue(session_id, limit=1):
    """Pop pending URLs from the queue for a specific session.
    Returns list of dicts with url, origin_url, depth.
    """
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, url, origin_url, depth FROM queue WHERE session_id = ? AND status = 'pending' LIMIT ?",
        (session_id, limit)
    ).fetchall()
    if rows:
        ids = [r["id"] for r in rows]
        placeholders = ",".join("?" * len(ids))
        conn.execute(f"DELETE FROM queue WHERE id IN ({placeholders})", ids)
        conn.commit()
    return [dict(r) for r in rows]


def get_queue_depth(session_id=None):
    """Get the number of pending URLs in the queue."""
    conn = _get_conn()
    if session_id:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM queue WHERE session_id = ? AND status = 'pending'",
            (session_id,)
        ).fetchone()
    else:
        row = conn.execute("SELECT COUNT(*) as cnt FROM queue WHERE status = 'pending'").fetchone()
    return row["cnt"]


def get_total_pages():
    """Get total number of crawled pages."""
    conn = _get_conn()
    row = conn.execute("SELECT COUNT(*) as cnt FROM pages").fetchone()
    return row["cnt"]


def get_active_sessions():
    """Get all running crawl sessions."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, origin_url, max_depth, status, created_at, pages_crawled FROM crawl_sessions WHERE status = 'running'"
    ).fetchall()
    return [dict(r) for r in rows]


def get_all_sessions():
    """Get all crawl sessions."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, origin_url, max_depth, status, created_at, pages_crawled FROM crawl_sessions ORDER BY id DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def get_pending_sessions():
    """Get sessions that have pending queue items (for resume)."""
    conn = _get_conn()
    rows = conn.execute("""
        SELECT DISTINCT cs.id, cs.origin_url, cs.max_depth, cs.status, cs.created_at, cs.pages_crawled
        FROM crawl_sessions cs
        JOIN queue q ON q.session_id = cs.id
        WHERE q.status = 'pending' AND cs.status != 'done'
    """).fetchall()
    return [dict(r) for r in rows]


def search_pages(query):
    """Search pages by keyword in title and body_text.
    Returns list of dicts with url, origin_url, depth, title, body_text.
    """
    conn = _get_conn()
    words = query.lower().split()
    if not words:
        return []

    # Use LIKE for each word, matching any page that contains all words
    conditions = []
    params = []
    for word in words:
        conditions.append("(LOWER(title) LIKE ? OR LOWER(body_text) LIKE ?)")
        params.extend([f"%{word}%", f"%{word}%"])

    where_clause = " AND ".join(conditions)
    rows = conn.execute(
        f"SELECT url, origin_url, depth, title, body_text FROM pages WHERE {where_clause}",
        params
    ).fetchall()
    return [dict(r) for r in rows]


def get_all_pages():
    """Get all crawled pages (for building inverted index)."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT url, origin_url, depth, title, body_text FROM pages"
    ).fetchall()
    return [dict(r) for r in rows]


def clear_all():
    """Delete all data from all tables (pages, queue, sessions)."""
    conn = _get_conn()
    conn.executescript("""
        DELETE FROM pages;
        DELETE FROM queue;
        DELETE FROM crawl_sessions;
        DELETE FROM sqlite_sequence;
    """)
    conn.commit()
    # Execute VACUUM outside the script/transaction to reclaim disk space
    conn.execute("VACUUM")

