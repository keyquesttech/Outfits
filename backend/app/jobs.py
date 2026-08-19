"""Tiny background worker.

A SQLite table plus one daemon thread replaces Redis and a queue process. AI
calls are the only slow work, and there is exactly one user, so a serial worker
is the right size for the problem.
"""

import json
import threading
import time
import traceback

from . import db, images
from .ai import get_provider
from .constants import DEFAULT_WASH_AFTER_WEARS, NO_WASH_CATEGORIES

POLL_SECONDS = 2
_worker: threading.Thread | None = None
_stop = threading.Event()


def enqueue(kind: str, item_id: int | None = None, payload: dict | None = None) -> int:
    return db.execute(
        "INSERT INTO jobs(item_id, kind, status, payload) VALUES (?,?,'queued',?)",
        (item_id, kind, db.dumps(payload or {})),
    )


def _finish(job_id: int, status: str, result=None, error: str | None = None) -> None:
    db.execute(
        "UPDATE jobs SET status = ?, result = ?, error = ?, updated_at = datetime('now') "
        "WHERE id = ?",
        (status, db.dumps(result) if result is not None else None, error, job_id),
    )


def _apply_analysis(item_id: int, data: dict, provider_name: str) -> dict:
    """Write AI-derived fields, but never overwrite something already set by hand."""
    row = db.query_one("SELECT * FROM items WHERE id = ?", (item_id,))
    if not row:
        return {}
    updates: dict = {}

    def maybe(field, value, blank=(None, "", 0)):
        if value in (None, ""):
            return
        if row.get(field) in blank or (field == "name" and str(row.get("name", "")).startswith("Untitled")):
            updates[field] = value

    maybe("name", data.get("name"))
    maybe("category", data.get("category"))
    maybe("subcategory", data.get("subcategory"))
    maybe("brand", data.get("brand"))
    maybe("material", data.get("material"))
    maybe("pattern", data.get("pattern"))
    maybe("colour_primary", data.get("colour_primary"))
    maybe("colour_secondary", data.get("colour_secondary"))
    if data.get("warmth") is not None:
        updates["warmth"] = max(0, min(10, int(data["warmth"])))
    if data.get("formality") is not None:
        updates["formality"] = max(1, min(5, int(data["formality"])))
    if data.get("seasons"):
        updates["seasons"] = db.dumps(data["seasons"])
    if data.get("wind_proof") is not None:
        updates["wind_proof"] = 1 if data["wind_proof"] else 0
    if data.get("water_proof") is not None:
        updates["water_proof"] = 1 if data["water_proof"] else 0

    category = updates.get("category", row.get("category"))
    if row.get("wash_after_wears") is None and category:
        updates["wash_after_wears"] = (
            0 if category in NO_WASH_CATEGORIES else DEFAULT_WASH_AFTER_WEARS.get(category, 3)
        )

    updates["ai_provider"] = provider_name
    updates["ai_confidence"] = data.get("confidence")

    sets = ", ".join(f"{k} = ?" for k in updates)
    db.execute(
        f"UPDATE items SET {sets}, updated_at = datetime('now') WHERE id = ?",
        (*updates.values(), item_id),
    )
    return updates


def _apply_care(item_id: int, data: dict, source: str) -> None:
    db.execute(
        "INSERT INTO care_instructions(item_id, wash_temp, wash_cycle, hand_wash_only, "
        "do_not_wash, tumble_dry, iron_temp, bleach, dry_clean, colour_group, raw_symbols, "
        "source, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,datetime('now')) "
        "ON CONFLICT(item_id) DO UPDATE SET wash_temp=excluded.wash_temp, "
        "wash_cycle=excluded.wash_cycle, hand_wash_only=excluded.hand_wash_only, "
        "do_not_wash=excluded.do_not_wash, tumble_dry=excluded.tumble_dry, "
        "iron_temp=excluded.iron_temp, bleach=excluded.bleach, dry_clean=excluded.dry_clean, "
        "colour_group=excluded.colour_group, raw_symbols=excluded.raw_symbols, "
        "source=excluded.source, updated_at=datetime('now')",
        (
            item_id, data.get("wash_temp"), data.get("wash_cycle"),
            1 if data.get("hand_wash_only") else 0, 1 if data.get("do_not_wash") else 0,
            data.get("tumble_dry"), data.get("iron_temp"), data.get("bleach"),
            data.get("dry_clean"), data.get("colour_group"),
            db.dumps(data.get("raw_symbols") or []), source,
        ),
    )


def run_job(job: dict) -> None:
    kind = job["kind"]
    item_id = job["item_id"]
    payload = db.loads(job.get("payload"), {})
    provider = get_provider()

    if not provider.available:
        _finish(job["id"], "skipped", error="No AI provider configured")
        return

    row = db.query_one("SELECT * FROM items WHERE id = ?", (item_id,)) if item_id else None
    source_path = payload.get("image_path") or (row or {}).get("image_path")
    blob = images.photo_bytes(source_path) if source_path else None
    if kind in ("analyse_item", "care_label", "cutout") and not blob:
        _finish(job["id"], "failed", error="Photo not found")
        return

    if kind == "analyse_item":
        data = provider.analyse_item(blob)
        if not data:
            _finish(job["id"], "failed", error="Provider returned nothing")
            return
        applied = _apply_analysis(item_id, data, provider.name)
        _finish(job["id"], "done", {"analysis": data, "applied": list(applied)})

    elif kind == "care_label":
        data = provider.read_care_label(blob)
        if not data:
            _finish(job["id"], "failed", error="Provider returned nothing")
            return
        _apply_care(item_id, data, provider.name)
        _finish(job["id"], "done", {"care": data})

    elif kind == "cutout":
        png = provider.remove_background(blob)
        if not png:
            _finish(job["id"], "skipped", error="Background removal unavailable")
            return
        rel = images.save_cutout(png)
        db.execute("UPDATE items SET cutout_path = ?, updated_at = datetime('now') WHERE id = ?",
                   (rel, item_id))
        _finish(job["id"], "done", {"cutout_path": rel})

    else:
        _finish(job["id"], "failed", error=f"Unknown job kind: {kind}")


def _loop() -> None:
    while not _stop.is_set():
        try:
            job = db.query_one(
                "SELECT * FROM jobs WHERE status = 'queued' ORDER BY id LIMIT 1"
            )
            if not job:
                _stop.wait(POLL_SECONDS)
                continue
            db.execute("UPDATE jobs SET status = 'running', updated_at = datetime('now') "
                       "WHERE id = ?", (job["id"],))
            run_job(job)
        except Exception:
            try:
                _finish(job["id"], "failed", error=traceback.format_exc(limit=3))
            except Exception:
                pass
            time.sleep(1)


def start() -> None:
    global _worker
    if _worker and _worker.is_alive():
        return
    # Anything left 'running' from a previous process is orphaned; requeue it.
    db.execute("UPDATE jobs SET status = 'queued' WHERE status = 'running'")
    _stop.clear()
    _worker = threading.Thread(target=_loop, name="outfits-jobs", daemon=True)
    _worker.start()


def stop() -> None:
    _stop.set()


def status() -> dict:
    rows = db.query("SELECT status, COUNT(*) AS count FROM jobs GROUP BY status")
    return {
        "worker_alive": bool(_worker and _worker.is_alive()),
        "counts": {r["status"]: r["count"] for r in rows},
        "recent": db.query("SELECT * FROM jobs ORDER BY id DESC LIMIT 15"),
    }
