import json
import sqlite3
import threading
from pathlib import Path

from . import config

_local = threading.local()
_schema_lock = threading.Lock()
_schema_done = False


# Columns added or removed after the first release. The schema file is the
# source of truth; this brings an existing database into line with it.
ADDED_COLUMNS = {"items": {"fit": "TEXT"}}
DROPPED_COLUMNS = {"items": ["price", "currency", "purchase_date"]}


def _migrate(conn: sqlite3.Connection) -> None:
    for table, columns in ADDED_COLUMNS.items():
        existing = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        for name, decl in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")
    for table, columns in DROPPED_COLUMNS.items():
        existing = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        for name in columns:
            if name in existing:
                conn.execute(f"ALTER TABLE {table} DROP COLUMN {name}")
    conn.commit()


def _apply_schema(conn: sqlite3.Connection) -> None:
    sql = (Path(__file__).parent / "schema.sql").read_text()
    conn.executescript(sql)
    _migrate(conn)
    for key, value in config.DEFAULT_SETTINGS.items():
        conn.execute("INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (key, value))
    conn.commit()


def get_conn() -> sqlite3.Connection:
    """One connection per thread. WAL lets the worker write while requests read."""
    global _schema_done
    conn = getattr(_local, "conn", None)
    if conn is None:
        config.ensure_dirs()
        conn = sqlite3.connect(config.DB_PATH, timeout=15, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
        with _schema_lock:
            if not _schema_done:
                _apply_schema(conn)
                _schema_done = True
    return conn


def query(sql: str, params=()) -> list[dict]:
    return [dict(r) for r in get_conn().execute(sql, params).fetchall()]


def query_one(sql: str, params=()) -> dict | None:
    row = get_conn().execute(sql, params).fetchone()
    return dict(row) if row else None


def execute(sql: str, params=()) -> int:
    conn = get_conn()
    cur = conn.execute(sql, params)
    conn.commit()
    return cur.lastrowid


def executemany(sql: str, seq) -> None:
    conn = get_conn()
    conn.executemany(sql, seq)
    conn.commit()


def get_setting(key: str, default: str = "") -> str:
    row = query_one("SELECT value FROM settings WHERE key = ?", (key,))
    return row["value"] if row and row["value"] is not None else default


def set_setting(key: str, value: str) -> None:
    execute(
        "INSERT INTO settings(key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def all_settings() -> dict:
    return {r["key"]: r["value"] for r in query("SELECT key, value FROM settings")}


def loads(value, fallback):
    """Columns holding JSON are text; decode defensively."""
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return fallback


def dumps(value) -> str | None:
    return json.dumps(value) if value is not None else None
