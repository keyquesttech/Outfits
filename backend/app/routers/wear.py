from datetime import date

from fastapi import APIRouter, HTTPException

from .. import db, recommend, wash, weather
from ..models import WearIn
from ..serializers import load_items

router = APIRouter(prefix="/api/wear", tags=["wear"])


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
    if payload.outfit_id and not item_ids:
        item_ids = [r["item_id"] for r in db.query(
            "SELECT item_id FROM outfit_items WHERE outfit_id = ?", (payload.outfit_id,)
        )]
    if not item_ids:
        raise HTTPException(400, "Log at least one item, or an outfit that has items")

    worn_on = payload.worn_on or date.today().isoformat()
    temp_c, apparent_c = payload.temp_c, payload.apparent_c
    condition = payload.condition

    # Only stamp live conditions on a wear logged for today. Back-filling last
    # Tuesday with this afternoon's weather would poison the calibration, which
    # learns from the gap between what you wore and how warm it actually was.
    if payload.use_weather and apparent_c is None and worn_on == date.today().isoformat():
        current = (weather.fetch().get("current") or {})
        temp_c = current.get("temp_c")
        apparent_c = current.get("apparent_c")
        condition = (current.get("condition") or {}).get("label")

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
        "updated_items": updated,
        "now_needing_wash": [i["id"] for i in updated if i["needs_wash"]],
        "personal_offset": offset,
    }


@router.post("/{wear_id}/comfort")
def rate_comfort(wear_id: int, verdict: int):
    """-1 too cold, 0 just right, 1 too hot. This is what calibrates the recommender."""
    if verdict not in (-1, 0, 1):
        raise HTTPException(400, "verdict must be -1, 0 or 1")
    row = db.query_one("SELECT * FROM wear_log WHERE id = ?", (wear_id,))
    if not row:
        raise HTTPException(404, "Wear log not found")
    apparent = row["apparent_c"]
    if apparent is None:
        raise HTTPException(400, "That wear has no weather recorded, so it cannot calibrate")
    ids = [r["item_id"] for r in db.query(
        "SELECT item_id FROM wear_log_items WHERE wear_log_id = ?", (wear_id,)
    )]
    db.execute("UPDATE wear_log SET comfort_rating = ? WHERE id = ?", (verdict, wear_id))
    offset = recommend.record_comfort(
        apparent, recommend.outfit_warmth(load_items(ids)), verdict, wear_id
    )
    return {"wear_id": wear_id, "verdict": verdict, "personal_offset": round(offset, 2)}


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
    if row.get("outfit_id"):
        db.execute("UPDATE outfits SET times_worn = MAX(0, times_worn - 1) WHERE id = ?",
                   (row["outfit_id"],))
    db.execute("DELETE FROM wear_log WHERE id = ?", (wear_id,))
    return {"deleted": wear_id, "reverted_items": ids}
