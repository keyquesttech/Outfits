"""Washing engine.

Wear counts drive status. Once an item passes its threshold it needs laundering,
and the laundry view groups everything dirty into loads that can actually go in
the machine together — same temperature band, compatible colour group, delicates
kept apart.
"""

from datetime import date

from . import categories, colours, db
from .serializers import item_out, wash_threshold

# A load is defined by the machine settings it needs.
TEMP_BANDS = [(0, 30, "30"), (31, 40, "40"), (41, 60, "60"), (61, 95, "95")]


def temp_band(temp: int | None) -> str:
    if temp is None:
        return "30"
    for lo, hi, label in TEMP_BANDS:
        if lo <= temp <= hi:
            return label
    return "30"


def default_threshold(category: str) -> int:
    known = categories.get(category)
    return int(known["wash_after_wears"]) if known else 3


def refresh_status(item_id: int) -> dict | None:
    """Recompute an item's status from its wear counter."""
    row = db.query_one("SELECT * FROM items WHERE id = ?", (item_id,))
    if not row:
        return None
    threshold = wash_threshold(row)
    worn = int(row["wears_since_wash"] or 0)
    status = row["status"]

    # A threshold of zero is what "never washed" means — jewellery, watches,
    # glasses, bags, and any category the user sets to zero.
    if threshold <= 0:
        status = "clean"
    elif status in ("in_wash", "airing"):
        pass  # user-driven states are left alone
    elif worn >= threshold:
        status = "needs_wash"
    elif worn > 0:
        status = "worn"
    else:
        status = "clean"

    db.execute("UPDATE items SET status = ?, updated_at = datetime('now') WHERE id = ?",
               (status, item_id))
    row["status"] = status
    return item_out(row)


def register_wear(item_ids: list[int], worn_on: str | None = None) -> list[dict]:
    worn_on = worn_on or date.today().isoformat()
    updated = []
    for item_id in item_ids:
        db.execute(
            "UPDATE items SET wears_since_wash = wears_since_wash + 1, "
            "total_wears = total_wears + 1, last_worn = ?, "
            "updated_at = datetime('now') WHERE id = ?",
            (worn_on, item_id),
        )
        result = refresh_status(item_id)
        if result:
            updated.append(result)
    return updated


def undo_wear(item_ids: list[int]) -> None:
    for item_id in item_ids:
        db.execute(
            "UPDATE items SET wears_since_wash = MAX(0, wears_since_wash - 1), "
            "total_wears = MAX(0, total_wears - 1), updated_at = datetime('now') "
            "WHERE id = ?",
            (item_id,),
        )
        refresh_status(item_id)


def mark_washed(item_ids: list[int], washed_on: str | None = None,
                program: str | None = None, temp_c: int | None = None,
                notes: str | None = None) -> int:
    """Record a laundry load and reset the items in it."""
    washed_on = washed_on or date.today().isoformat()
    batch_id = db.execute(
        "INSERT INTO wash_batches(washed_on, program, temp_c, notes) VALUES (?,?,?,?)",
        (washed_on, program, temp_c, notes),
    )
    db.executemany(
        "INSERT OR IGNORE INTO wash_batch_items(batch_id, item_id) VALUES (?,?)",
        [(batch_id, i) for i in item_ids],
    )
    for item_id in item_ids:
        db.execute(
            "UPDATE items SET wears_since_wash = 0, status = 'clean', last_washed = ?, "
            "updated_at = datetime('now') WHERE id = ?",
            (washed_on, item_id),
        )
    return batch_id


def set_status(item_id: int, status: str) -> dict | None:
    db.execute("UPDATE items SET status = ?, updated_at = datetime('now') WHERE id = ?",
               (status, item_id))
    if status == "clean":
        db.execute("UPDATE items SET wears_since_wash = 0 WHERE id = ?", (item_id,))
    row = db.query_one("SELECT * FROM items WHERE id = ?", (item_id,))
    return item_out(row) if row else None


def _load_key(item: dict, care: dict | None) -> tuple:
    """The machine settings this item demands."""
    care = care or {}
    if care.get("do_not_wash"):
        return ("do_not_wash", "-")
    if care.get("dry_clean") and care["dry_clean"] != "no":
        return ("dry_clean", "-")
    if care.get("hand_wash_only"):
        return ("hand_wash", "-")
    cycle = care.get("wash_cycle") or "normal"
    if cycle in ("delicate", "wool"):
        return (cycle, temp_band(care.get("wash_temp") or 30))
    group = care.get("colour_group") or colours.colour_group(item.get("colour_primary"))
    return (group, temp_band(care.get("wash_temp")))


LOAD_LABELS = {
    "do_not_wash": "Do not wash",
    "dry_clean": "Dry clean",
    "hand_wash": "Hand wash",
    "delicate": "Delicates",
    "wool": "Wool cycle",
    "whites": "Whites",
    "lights": "Lights",
    "darks": "Darks",
    "colours": "Colours",
}


def laundry_plan() -> dict:
    """Everything currently dirty, grouped into runnable loads."""
    rows = db.query(
        "SELECT * FROM items WHERE is_active = 1 AND status IN ('needs_wash','in_wash') "
        "ORDER BY last_worn DESC"
    )
    care_rows = {c["item_id"]: c for c in db.query("SELECT * FROM care_instructions")}
    catalogue = categories.by_key()

    loads: dict[tuple, dict] = {}
    for row in rows:
        item = item_out(row, catalogue)
        care = care_rows.get(item["id"])
        key = _load_key(item, care)
        group, temp = key
        load = loads.setdefault(key, {
            "key": f"{group}-{temp}",
            "group": group,
            "label": LOAD_LABELS.get(group, group.title()),
            "temp_c": None if temp == "-" else int(temp),
            "machine_wash": group not in ("do_not_wash", "dry_clean", "hand_wash"),
            "items": [],
        })
        load["items"].append(item)

    ordered = sorted(loads.values(), key=lambda l: (-len(l["items"]), l["label"]))
    for load in ordered:
        load["count"] = len(load["items"])
    return {
        "loads": ordered,
        "dirty_count": len(rows),
        "generated_on": date.today().isoformat(),
    }


def due_soon(within: int = 1) -> list[dict]:
    """Items about to cross their threshold — worth knowing before you plan a week.

    Only counts things actually worn since their last wash. A clean sock sitting
    at 0 of 1 wears is not "nearly dirty", it is clean.
    """
    rows = db.query(
        "SELECT * FROM items WHERE is_active = 1 AND status IN ('worn','clean') "
        "AND wears_since_wash > 0"
    )
    catalogue = categories.by_key()
    out = []
    for row in rows:
        item = item_out(row, catalogue)
        if item["launderable"] and item["wears_left"] is not None and 0 < item["wears_left"] <= within:
            out.append(item)
    return sorted(out, key=lambda i: i["wears_left"])
