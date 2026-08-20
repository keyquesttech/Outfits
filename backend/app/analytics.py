"""Wardrobe analytics — what you actually wear, versus what you actually own."""

from collections import Counter
from datetime import date, timedelta

from . import colours, db, taste
from .serializers import item_out


def summary() -> dict:
    totals = db.query_one(
        "SELECT COUNT(*) AS total, "
        "SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) AS active, "
        "SUM(total_wears) AS wears FROM items"
    ) or {}
    by_category = db.query(
        "SELECT category, COUNT(*) AS count FROM items WHERE is_active = 1 "
        "GROUP BY category ORDER BY count DESC"
    )
    outfits = db.query_one("SELECT COUNT(*) AS count FROM outfits") or {}
    logs = db.query_one("SELECT COUNT(*) AS count FROM wear_log") or {}
    wears = totals.get("wears") or 0
    return {
        "total_items": totals.get("total") or 0,
        "active_items": totals.get("active") or 0,
        "total_wears": wears,
        "outfits": outfits.get("count") or 0,
        "wear_logs": logs.get("count") or 0,
        "by_category": by_category,
    }


def most_worn(limit: int = 10) -> list[dict]:
    rows = db.query(
        "SELECT * FROM items WHERE is_active = 1 AND total_wears > 0 "
        "ORDER BY total_wears DESC LIMIT ?", (limit,)
    )
    return [item_out(r) for r in rows]


def least_worn(limit: int = 10) -> list[dict]:
    rows = db.query(
        "SELECT * FROM items WHERE is_active = 1 ORDER BY total_wears ASC, id ASC LIMIT ?",
        (limit,),
    )
    return [item_out(r) for r in rows]


def neglected(days: int = 90, limit: int = 20) -> list[dict]:
    """Owned but untouched — the honest part of the wardrobe."""
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    rows = db.query(
        "SELECT * FROM items WHERE is_active = 1 "
        "AND (last_worn IS NULL OR last_worn < ?) ORDER BY total_wears ASC LIMIT ?",
        (cutoff, limit),
    )
    return [item_out(r) for r in rows]


def colour_distribution() -> list[dict]:
    """What the wardrobe is actually made of, by colour.

    Grouped in Python rather than by SQL: the column holds whatever was typed,
    so "Gray", "grey" and "N/A" used to be three separate bars. Canonicalising
    first makes the chart count garments instead of counting spellings, and
    carries the swatch so the bars can be shown in the colour they describe.
    """
    rows = db.query(
        "SELECT colour_primary AS colour, COUNT(*) AS count, SUM(total_wears) AS wears "
        "FROM items WHERE is_active = 1 AND colour_primary IS NOT NULL "
        "AND TRIM(colour_primary) != '' GROUP BY colour_primary"
    )
    grouped: dict[str, dict] = {}
    for row in rows:
        reading = colours.describe(row["colour"])
        slot = grouped.setdefault(reading["name"], {
            "colour": reading["name"], "count": 0, "wears": 0,
            "hex": reading["hex"], "known": reading["known"],
        })
        slot["count"] += row["count"]
        slot["wears"] += row["wears"] or 0
    return sorted(grouped.values(), key=lambda c: (-c["count"], c["colour"]))


def top_combinations(limit: int = 10) -> list[dict]:
    """Item pairs that keep showing up together."""
    logs = db.query("SELECT wear_log_id, item_id FROM wear_log_items ORDER BY wear_log_id")
    grouped: dict[int, list[int]] = {}
    for row in logs:
        grouped.setdefault(row["wear_log_id"], []).append(row["item_id"])

    pairs: Counter = Counter()
    for items in grouped.values():
        ordered = sorted(set(items))
        for i, a in enumerate(ordered):
            for b in ordered[i + 1:]:
                pairs[(a, b)] += 1

    if not pairs:
        return []
    ids = {i for pair in pairs for i in pair}
    marks = ",".join("?" * len(ids))
    lookup = {r["id"]: item_out(r) for r in
              db.query(f"SELECT * FROM items WHERE id IN ({marks})", tuple(ids))}

    out = []
    for (a, b), count in pairs.most_common(limit):
        if a in lookup and b in lookup and count > 1:
            out.append({"count": count, "items": [lookup[a], lookup[b]]})
    return out


def wear_timeline(weeks: int = 12) -> list[dict]:
    """Items worn per day.

    Counting wear_log rows instead would read 1 on almost every day, since one
    outfit is one row — a flat chart that says nothing. Counting the garments
    shows how much of the wardrobe actually moved.
    """
    cutoff = (date.today() - timedelta(weeks=weeks)).isoformat()
    return db.query(
        "SELECT wear_log.worn_on, COUNT(wear_log_items.item_id) AS count, "
        "COUNT(DISTINCT wear_log.id) AS outfits "
        "FROM wear_log LEFT JOIN wear_log_items "
        "ON wear_log.id = wear_log_items.wear_log_id "
        "WHERE wear_log.worn_on >= ? GROUP BY wear_log.worn_on "
        "ORDER BY wear_log.worn_on",
        (cutoff,),
    )


def comfort_calibration() -> dict:
    rows = db.query("SELECT verdict, COUNT(*) AS count FROM comfort_feedback GROUP BY verdict")
    labels = {-1: "too cold", 0: "just right", 1: "too hot"}
    from .recommend import personal_offset
    return {
        "counts": [{"verdict": labels.get(r["verdict"], "?"), "count": r["count"]} for r in rows],
        "offset": round(personal_offset(), 2),
        "total": sum(r["count"] for r in rows),
    }


def gaps() -> list[dict]:
    """Categories that are thin enough to limit what can be suggested."""
    from . import categories
    catalogue = categories.by_key()
    counts = {r["category"]: r["count"] for r in db.query(
        "SELECT category, COUNT(*) AS count FROM items WHERE is_active = 1 GROUP BY category"
    )}
    essential = {"top": 3, "bottom": 2, "footwear": 2, "outerwear": 1, "mid": 1}
    out = []
    for category, want in essential.items():
        have = counts.get(category, 0)
        if category == "top":
            have += counts.get("shirt", 0) + counts.get("dress", 0)
        if category == "mid":
            have += counts.get("knitwear", 0)
        if have < want:
            out.append({"category": category, "have": have, "suggested": want,
                        "layer": (catalogue.get(category) or {}).get("layer")})
    return out


def full_report() -> dict:
    return {
        "summary": summary(),
        "taste": taste.summary(),
        "most_worn": most_worn(),
        "least_worn": least_worn(),
        "neglected": neglected(),
        "colours": colour_distribution(),
        "combinations": top_combinations(),
        "timeline": wear_timeline(),
        "comfort": comfort_calibration(),
        "gaps": gaps(),
    }
