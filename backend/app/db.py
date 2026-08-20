import json
import sqlite3
import threading
from pathlib import Path

from . import colours, config

_local = threading.local()
_schema_lock = threading.Lock()
_schema_done = False


# Columns added or removed after the first release. The schema file is the
# source of truth; this brings an existing database into line with it.
ADDED_COLUMNS = {
    "items": {
        "fit": "TEXT",
        "damage": "TEXT NOT NULL DEFAULT 'none'",
        "takes_belt": "INTEGER NOT NULL DEFAULT 1",
    },
    "outfits": {
        "is_base": "INTEGER NOT NULL DEFAULT 0",
    },
}
DROPPED_COLUMNS = {
    "items": ["price", "currency", "purchase_date",
              # The laundry half of the app was removed; wear counts stay.
              "status", "wears_since_wash", "wash_after_wears", "last_washed"],
    "categories": ["wash_after_wears"],
}
# Tables belonging to removed features. Dropped outright, not archived — the
# uninstall of a feature should not leave furniture behind.
DROPPED_TABLES = ["care_instructions", "wash_batches", "wash_batch_items"]
# Indexes over dropped columns have to go first, or the column drop fails on
# the index that still mentions it.
DROPPED_INDEXES = ["idx_items_status", "idx_wash_batch_items_item"]


def _migrate(conn: sqlite3.Connection) -> None:
    for table, columns in ADDED_COLUMNS.items():
        existing = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        for name, decl in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")
    for index in DROPPED_INDEXES:
        conn.execute(f"DROP INDEX IF EXISTS {index}")
    for table, columns in DROPPED_COLUMNS.items():
        existing = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        for name in columns:
            if name in existing:
                conn.execute(f"ALTER TABLE {table} DROP COLUMN {name}")
    for table in DROPPED_TABLES:
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.commit()


# Bumped when the colour vocabulary changes in a way that needs stored values
# rewritten. The current value is recorded in settings, so the pass runs once.
COLOUR_VOCAB_VERSION = "1"


def _normalise_colours(conn: sqlite3.Connection) -> int:
    """Rewrite stored colour names into the app's vocabulary, once.

    Colours were free text, so a wardrobe built before this holds "Gray",
    "Dark Red", "N/A" and "Blue/Green" — none of which the laundry sorter, the
    colour filter or the outfit matcher could recognise. This brings them into
    line without touching anything it does not understand: an unknown word is
    left exactly as typed.
    """
    row = conn.execute("SELECT value FROM settings WHERE key = 'colour_vocab'").fetchone()
    if row and row[0] == COLOUR_VOCAB_VERSION:
        return 0

    changed = 0
    for item in conn.execute(
        "SELECT id, colour_primary, colour_secondary FROM items"
    ).fetchall():
        item_id, primary, secondary = item[0], item[1], item[2]
        # "Blue/Green" is two colours. If the second slot is free, that is where
        # the second one belongs rather than being discarded.
        parts = colours.split_colours(primary)
        new_primary = colours.normalise(primary)
        new_secondary = colours.normalise(secondary)
        if len(parts) > 1:
            new_primary = parts[0]
            if not new_secondary:
                new_secondary = parts[1]
        if colours.same_shade(new_primary, new_secondary):
            new_secondary = None
        if (new_primary, new_secondary) != (primary, secondary):
            conn.execute(
                "UPDATE items SET colour_primary = ?, colour_secondary = ? WHERE id = ?",
                (new_primary, new_secondary, item_id),
            )
            changed += 1

    conn.execute("INSERT INTO settings(key, value) VALUES ('colour_vocab', ?) "
                 "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                 (COLOUR_VOCAB_VERSION,))
    return changed


def _apply_schema(conn: sqlite3.Connection) -> None:
    sql = (Path(__file__).parent / "schema.sql").read_text()
    conn.executescript(sql)
    _migrate(conn)
    for key, value in config.DEFAULT_SETTINGS.items():
        conn.execute("INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (key, value))
    _normalise_colours(conn)
    # Imported here rather than at module scope: `categories` reads through the
    # helpers below, so importing it at the top would be a cycle.
    from . import categories

    categories.seed(conn)
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
