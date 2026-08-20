from datetime import date

from fastapi import APIRouter, HTTPException

from .. import db, recommend, wash, weather
from ..models import WearIn, WearPatch
from ..serializers import load_items

router = APIRouter(prefix="/api/wear", tags=["wear"])


def _current_conditions() -> dict:
    """What resolve_outfit scores against: the weather out there right now."""
    data = weather.fetch()
    current = data.get("current") or {}
    today = data.get("today") or {}
    return {
        "apparent_c": current.get("apparent_c"),
        "rain_chance": today.get("rain_chance"),
        "wind_kph": current.get("wind_kph"),
    }


def _weather_for(worn_on: str) -> tuple:
    """(temp, apparent, condition) for the day a wear happened.

    Today comes from the live forecast; any earlier day is looked up in the
    historical record, so a back-dated outfit is scored against the weather it
    was actually worn in.
    """
    if worn_on == date.today().isoformat():
        current = (weather.fetch().get("current") or {})
        return (current.get("temp_c"), current.get("apparent_c"),
                (current.get("condition") or {}).get("label"))
    past = weather.on_date(worn_on)
    if not past.get("available"):
        return (None, None, None)
    return (past.get("temp_c"), past.get("apparent_c"),
            (past.get("condition") or {}).get("label"))


def _refresh_last_worn(item_ids: list[int]) -> None:
    """Recompute `items.last_worn` from the log.

    The column is a cache of the newest wear, maintained forward-only when a
    wear is recorded. Moving a wear to a different day can make it wrong in
    either direction, so it is recomputed from the rows that actually exist.
    """
    if not item_ids:
        return
    marks = ",".join("?" * len(item_ids))
    db.execute(
        f"UPDATE items SET last_worn = (SELECT MAX(wl.worn_on) FROM wear_log wl "
        f"JOIN wear_log_items wli ON wli.wear_log_id = wl.id "
        f"WHERE wli.item_id = items.id) WHERE id IN ({marks})",
        tuple(item_ids),
    )


def _hydrate(row: dict) -> dict:
    log = dict(row)
    ids = [r["item_id"] for r in db.query(
        "SELECT item_id FROM wear_log_items WHERE wear_log_id = ?", (log["id"],)
    )]
    log["items"] = load_items(ids)
    log["item_ids"] = ids
    if log.get("outfit_id"):
        outfit = db.query_one("SELECT name FROM outfits WHERE id = ?", (log["outfit_id"],))
        log["outfit_name"] = outfit["name"] if outfit else None
    return log


@router.get("")
def list_wears(limit: int = 60, item_id: int | None = None):
    if item_id:
        rows = db.query(
            "SELECT wear_log.* FROM wear_log JOIN wear_log_items "
            "ON wear_log.id = wear_log_items.wear_log_id WHERE wear_log_items.item_id = ? "
            "ORDER BY worn_on DESC, wear_log.id DESC LIMIT ?", (item_id, limit)
        )
    else:
        rows = db.query(
            "SELECT * FROM wear_log ORDER BY worn_on DESC, id DESC LIMIT ?", (limit,)
        )
    return {"wears": [_hydrate(r) for r in rows]}


@router.post("", status_code=201)
def log_wear(payload: WearIn):
    """Record what was worn. This is what drives wear counts and the wash queue."""
    item_ids = list(dict.fromkeys(payload.item_ids))
    resolved = False
    if payload.outfit_id and not item_ids:
        saved_ids = [r["item_id"] for r in db.query(
            "SELECT item_id FROM outfit_items WHERE outfit_id = ?", (payload.outfit_id,)
        )]
        saved = load_items(saved_ids)
        # A saved outfit can hold alternatives — three tops, two shoes. Wearing
        # it wears one of each, chosen for today rather than all of them at once.
        conditions = _current_conditions() if payload.use_weather else {}
        tag_map = recommend.tags_by_item()
        for item in saved:
            item["tags"] = sorted(tag_map.get(item["id"], set()))
        chosen = recommend.resolve_outfit(saved, conditions, payload.occasion)
        item_ids = [i["id"] for i in chosen]
        resolved = len(item_ids) < len(saved_ids)
    if not item_ids:
        raise HTTPException(400, "Log at least one item, or an outfit that has items")

    worn_on = payload.worn_on or date.today().isoformat()
    try:
        date.fromisoformat(worn_on)
    except ValueError:
        raise HTTPException(400, "worn_on must be a date like 2026-08-19") from None
    if worn_on > date.today().isoformat():
        raise HTTPException(400, "That day has not happened yet")
    temp_c, apparent_c = payload.temp_c, payload.apparent_c
    condition = payload.condition

    # Live conditions belong only on a wear logged for today. Back-filling last
    # Tuesday with this afternoon's weather would poison the calibration, which
    # learns from the gap between what you wore and how warm it actually was —
    # so a past day gets that day's real weather looked up instead.
    if payload.use_weather and apparent_c is None:
        temp_c, apparent_c, condition = _weather_for(worn_on)

    log_id = db.execute(
        "INSERT INTO wear_log(worn_on, outfit_id, occasion, comfort_rating, rating, "
        "temp_c, apparent_c, condition, notes) VALUES (?,?,?,?,?,?,?,?,?)",
        (worn_on, payload.outfit_id, payload.occasion, payload.comfort_rating,
         payload.rating, temp_c, apparent_c, condition, payload.notes),
    )
    db.executemany(
        "INSERT OR IGNORE INTO wear_log_items(wear_log_id, item_id) VALUES (?,?)",
        [(log_id, i) for i in item_ids],
    )
    updated = wash.register_wear(item_ids, worn_on)

    if payload.outfit_id:
        db.execute("UPDATE outfits SET times_worn = times_worn + 1, last_worn = ? WHERE id = ?",
                   (worn_on, payload.outfit_id))

    offset = None
    if payload.comfort_rating is not None and apparent_c is not None:
        offset = recommend.record_comfort(
            apparent_c, recommend.outfit_warmth(load_items(item_ids)),
            payload.comfort_rating, log_id,
        )

    return {
        "wear": _hydrate(db.query_one("SELECT * FROM wear_log WHERE id = ?", (log_id,))),
        "resolved": resolved,
        "updated_items": updated,
        "now_needing_wash": [i["id"] for i in updated if i["needs_wash"]],
        "personal_offset": offset,
    }


def _record_comfort(wear_id: int, row: dict, verdict: int) -> float | None:
    """Store a comfort verdict, and calibrate with it when that is possible.

    Calibration compares how warm the outfit was against how warm it actually
    was outside, so a wear with no weather against it cannot contribute. That is
    not a reason to refuse the rating — a back-filled Tuesday is still worth
    recording — so the verdict is kept either way and only the calibration is
    skipped.
    """
    db.execute("UPDATE wear_log SET comfort_rating = ? WHERE id = ?", (verdict, wear_id))
    apparent = row.get("apparent_c")
    if apparent is None:
        return None
    ids = [r["item_id"] for r in db.query(
        "SELECT item_id FROM wear_log_items WHERE wear_log_id = ?", (wear_id,)
    )]
    return recommend.record_comfort(
        apparent, recommend.outfit_warmth(load_items(ids)), verdict, wear_id)


@router.patch("/{wear_id}")
def update_wear(wear_id: int, payload: WearPatch):
    """Feedback after the fact: how it felt, how much you liked it, what for.

    Everything here was settable only at the moment of logging, which is the one
    moment you cannot yet know how the day went.
    """
    row = db.query_one("SELECT * FROM wear_log WHERE id = ?", (wear_id,))
    if not row:
        raise HTTPException(404, "Wear log not found")

    fields = payload.model_dump(exclude_unset=True)
    offset = None
    if "comfort_rating" in fields:
        verdict = fields.pop("comfort_rating")
        if verdict is None:
            # Tapping the verdict you already gave takes it back. The feedback
            # row has to go with it, or the calibration keeps learning from an
            # answer that has been withdrawn.
            db.execute("UPDATE wear_log SET comfort_rating = NULL WHERE id = ?", (wear_id,))
            db.execute("DELETE FROM comfort_feedback WHERE wear_log_id = ?", (wear_id,))
            offset = recommend.personal_offset()
            db.set_setting("warmth_offset", f"{offset:.2f}")
        else:
            offset = _record_comfort(wear_id, row, int(verdict))

    # Replacing the items is a diff, not a rewrite: only what actually changed
    # touches the wear counters, so the unchanged pieces keep their history.
    items_changed = False
    affected: set[int] = set()
    if fields.get("item_ids") is not None:
        new_ids = list(dict.fromkeys(int(i) for i in fields.pop("item_ids")))
        if not new_ids:
            raise HTTPException(400, "A wear needs at least one item — delete the "
                                     "entry instead of emptying it")
        found = {i["id"] for i in load_items(new_ids)}
        missing = sorted(set(new_ids) - found)
        if missing:
            raise HTTPException(400, f"Unknown item id(s): {missing}")
        old_ids = [r["item_id"] for r in db.query(
            "SELECT item_id FROM wear_log_items WHERE wear_log_id = ?", (wear_id,))]
        added = [i for i in new_ids if i not in set(old_ids)]
        removed = [i for i in old_ids if i not in set(new_ids)]
        if added or removed:
            items_changed = True
            affected = set(old_ids) | set(new_ids)
            for item_id in removed:
                db.execute("DELETE FROM wear_log_items WHERE wear_log_id = ? AND item_id = ?",
                           (wear_id, item_id))
            db.executemany(
                "INSERT OR IGNORE INTO wear_log_items(wear_log_id, item_id) VALUES (?,?)",
                [(wear_id, i) for i in added])
            wash.undo_wear(removed)
            worn_on_target = fields.get("worn_on") or row["worn_on"]
            wash.register_wear(added, worn_on_target)
    else:
        fields.pop("item_ids", None)

    refresh_weather = fields.pop("refresh_weather", True)
    updates = {k: v for k, v in fields.items()
               if k in ("rating", "occasion", "notes", "worn_on")}

    moved = "worn_on" in updates and updates["worn_on"] != row["worn_on"]
    if moved:
        try:
            date.fromisoformat(updates["worn_on"])
        except (TypeError, ValueError):
            raise HTTPException(400, "worn_on must be a date like 2026-08-19") from None
        if updates["worn_on"] > date.today().isoformat():
            raise HTTPException(400, "That day has not happened yet")
        if refresh_weather:
            temp_c, apparent_c, condition = _weather_for(updates["worn_on"])
            updates.update({"temp_c": temp_c, "apparent_c": apparent_c,
                            "condition": condition})

    if updates:
        sets = ", ".join(f"{k} = ?" for k in updates)
        db.execute(f"UPDATE wear_log SET {sets} WHERE id = ?", (*updates.values(), wear_id))

    if moved or items_changed:
        ids = set(r["item_id"] for r in db.query(
            "SELECT item_id FROM wear_log_items WHERE wear_log_id = ?", (wear_id,)))
        _refresh_last_worn(sorted(ids | affected))
        # The comfort verdict was given against the old day's weather and the
        # old outfit's warmth; both may just have changed under it. Re-record it
        # so the calibration is not learning from a mismatch.
        fresh = db.query_one("SELECT * FROM wear_log WHERE id = ?", (wear_id,))
        if fresh.get("comfort_rating") is not None:
            offset = _record_comfort(wear_id, fresh, int(fresh["comfort_rating"]))
        row = fresh

    calibrated = offset is not None and row.get("apparent_c") is not None
    return {
        "wear": _hydrate(db.query_one("SELECT * FROM wear_log WHERE id = ?", (wear_id,))),
        "personal_offset": round(offset, 2) if offset is not None else None,
        "calibrated": calibrated,
    }


@router.post("/{wear_id}/comfort")
def rate_comfort(wear_id: int, verdict: int):
    """-1 too cold, 0 just right, 1 too hot. This is what calibrates the recommender."""
    if verdict not in (-1, 0, 1):
        raise HTTPException(400, "verdict must be -1, 0 or 1")
    row = db.query_one("SELECT * FROM wear_log WHERE id = ?", (wear_id,))
    if not row:
        raise HTTPException(404, "Wear log not found")
    offset = _record_comfort(wear_id, row, verdict)
    return {"wear_id": wear_id, "verdict": verdict,
            "personal_offset": round(offset, 2) if offset is not None else None,
            "calibrated": offset is not None}


@router.delete("/{wear_id}/items/{item_id}")
def remove_item_from_wear(wear_id: int, item_id: int):
    """Take one garment out of a logged wear, keeping the rest of it.

    For the common correction: the outfit was right except you did not actually
    put the belt on. Only that item's counters go back — and if it was the last
    one left, the entry itself goes, because a wear with nothing in it is not a
    record of anything.
    """
    row = db.query_one("SELECT * FROM wear_log WHERE id = ?", (wear_id,))
    if not row:
        raise HTTPException(404, "Wear log not found")
    ids = [r["item_id"] for r in db.query(
        "SELECT item_id FROM wear_log_items WHERE wear_log_id = ?", (wear_id,)
    )]
    if item_id not in ids:
        raise HTTPException(404, "That item is not in this wear")

    db.execute("DELETE FROM wear_log_items WHERE wear_log_id = ? AND item_id = ?",
               (wear_id, item_id))
    wash.undo_wear([item_id])
    _refresh_last_worn([item_id])

    remaining = [i for i in ids if i != item_id]
    if not remaining:
        return delete_wear(wear_id)

    # The comfort rating was given for a warmer or cooler outfit than what is
    # left, and the calibration reads that number. Keep it honest.
    db.execute("UPDATE comfort_feedback SET outfit_warmth = ? WHERE wear_log_id = ?",
               (recommend.outfit_warmth(load_items(remaining)), wear_id))
    return {"wear_id": wear_id, "removed": item_id,
            "wear": _hydrate(db.query_one("SELECT * FROM wear_log WHERE id = ?", (wear_id,)))}


@router.delete("/{wear_id}")
def delete_wear(wear_id: int):
    row = db.query_one("SELECT * FROM wear_log WHERE id = ?", (wear_id,))
    if not row:
        raise HTTPException(404, "Wear log not found")
    ids = [r["item_id"] for r in db.query(
        "SELECT item_id FROM wear_log_items WHERE wear_log_id = ?", (wear_id,)
    )]
    wash.undo_wear(ids)
    db.execute("DELETE FROM wear_log_items WHERE wear_log_id = ?", (wear_id,))
    _refresh_last_worn(ids)
    if row.get("outfit_id"):
        db.execute("UPDATE outfits SET times_worn = MAX(0, times_worn - 1) WHERE id = ?",
                   (row["outfit_id"],))
    db.execute("DELETE FROM wear_log WHERE id = ?", (wear_id,))
    return {"deleted": wear_id, "reverted_items": ids}
