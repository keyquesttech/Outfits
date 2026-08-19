from . import db
from .constants import CATEGORY_LAYERS, DEFAULT_WASH_AFTER_WEARS, NO_WASH_CATEGORIES


def photo_url(rel: str | None) -> str | None:
    return f"/photos/{rel}" if rel else None


def wash_threshold(item: dict) -> int:
    explicit = item.get("wash_after_wears")
    if explicit is not None:
        return int(explicit)
    return DEFAULT_WASH_AFTER_WEARS.get(item.get("category", ""), 3)


def item_out(row: dict) -> dict:
    item = dict(row)
    category = item.get("category", "")
    item["layer"] = CATEGORY_LAYERS.get(category, "accessory")
    item["palette"] = db.loads(item.pop("colour_palette", None), [])
    item["seasons"] = db.loads(item.get("seasons"), [])
    item["wind_proof"] = bool(item.get("wind_proof"))
    item["water_proof"] = bool(item.get("water_proof"))
    item["is_active"] = bool(item.get("is_active", 1))

    threshold = wash_threshold(item)
    launderable = category not in NO_WASH_CATEGORIES and threshold > 0
    item["launderable"] = launderable
    item["wash_threshold"] = threshold
    item["wears_left"] = max(0, threshold - int(item.get("wears_since_wash") or 0)) if launderable else None
    item["needs_wash"] = bool(launderable and int(item.get("wears_since_wash") or 0) >= threshold)

    item["image_url"] = photo_url(item.get("image_path"))
    item["thumb_url"] = photo_url(item.get("thumb_path")) or photo_url(item.get("image_path"))
    item["cutout_url"] = photo_url(item.get("cutout_path"))
    item["display_url"] = item["cutout_url"] or item["image_url"]

    price = item.get("price")
    worn = int(item.get("total_wears") or 0)
    item["cost_per_wear"] = round(price / worn, 2) if price and worn else None
    return item


def care_out(row: dict | None) -> dict | None:
    if not row:
        return None
    care = dict(row)
    care["hand_wash_only"] = bool(care.get("hand_wash_only"))
    care["do_not_wash"] = bool(care.get("do_not_wash"))
    care["raw_symbols"] = db.loads(care.get("raw_symbols"), [])
    return care


def outfit_out(row: dict, items: list[dict]) -> dict:
    outfit = dict(row)
    outfit["is_favourite"] = bool(outfit.get("is_favourite"))
    outfit["items"] = items
    outfit["total_warmth"] = sum(
        int(i.get("warmth") or 0) for i in items
        if i.get("layer") in ("bottom", "top", "mid", "outer", "footwear")
    )
    formalities = [int(i["formality"]) for i in items if i.get("formality")]
    outfit["formality"] = round(sum(formalities) / len(formalities), 1) if formalities else None
    outfit["needs_wash"] = any(i.get("needs_wash") for i in items)
    outfit["thumb_url"] = next((i["thumb_url"] for i in items if i.get("thumb_url")), None)
    return outfit


def load_items(ids: list[int]) -> list[dict]:
    if not ids:
        return []
    marks = ",".join("?" * len(ids))
    rows = db.query(f"SELECT * FROM items WHERE id IN ({marks})", tuple(ids))
    by_id = {r["id"]: item_out(r) for r in rows}
    return [by_id[i] for i in ids if i in by_id]
