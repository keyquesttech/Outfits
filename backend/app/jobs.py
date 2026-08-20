"""Tiny background worker.

A SQLite table plus one daemon thread replaces Redis and a queue process. AI
calls are the only slow work, and there is exactly one user, so a serial worker
is the right size for the problem.
"""

import json
import threading
import time
import traceback

from . import colours, db, images
from .ai import get_provider

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
        current = row.get(field)
        # "N/A" is not an answer someone gave, it is a field they left alone.
        if isinstance(current, str) and current.strip().lower() in colours.BLANKS:
            current = ""
        if current in blank or (field == "name" and str(row.get("name", "")).startswith("Untitled")):
            updates[field] = value

    maybe("name", data.get("name"))
    maybe("category", data.get("category"))
    maybe("subcategory", data.get("subcategory"))
    maybe("brand", data.get("brand"))
    maybe("material", data.get("material"))
    maybe("pattern", data.get("pattern"))
    # The model is asked for plain English and mostly obliges, but "Dark Red"
    # and "Gray" come back often enough that storing them raw would undo the
    # normalisation the manual path does.
    maybe("colour_primary", colours.normalise(data.get("colour_primary")))
    secondary = colours.normalise(data.get("colour_secondary"))
    if colours.same_shade(data.get("colour_primary"), secondary):
        secondary = None
    maybe("colour_secondary", secondary)
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

    updates["ai_provider"] = provider_name
    updates["ai_confidence"] = data.get("confidence")

    sets = ", ".join(f"{k} = ?" for k in updates)
    db.execute(
        f"UPDATE items SET {sets}, updated_at = datetime('now') WHERE id = ?",
        (*updates.values(), item_id),
    )
    return updates


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
    if kind in ("analyse_item", "cutout") and not blob:
        _finish(job["id"], "failed", error="Photo not found")
        return

    if kind == "analyse_item":
        data = provider.analyse_item(blob)
        if not data:
            _finish(job["id"], "failed", error="Provider returned nothing")
            return
        applied = _apply_analysis(item_id, data, provider.name)
        _finish(job["id"], "done", {"analysis": data, "applied": list(applied)})

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
