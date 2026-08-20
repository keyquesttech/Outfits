from . import categories, db


def photo_url(rel: str | None) -> str | None:
    return f"/photos/{rel}" if rel else None


def wash_threshold(item: dict, catalogue: dict | None = None) -> int:
    explicit = item.get("wash_after_wears")
    if explicit is not None:
        return int(explicit)
    catalogue = catalogue if catalogue is not None else categories.by_key()
    known = catalogue.get(item.get("category", ""))
    return int(known["wash_after_wears"]) if known else 3


def item_out(row: dict, catalogue: dict | None = None) -> dict:
    """Shape a row for the API.

    `catalogue` lets a caller serialising a whole list read the category table
    once instead of once per item.
    """
    item = dict(row)
    catalogue = catalogue if catalogue is not None else categories.by_key()
    category = item.get("category", "")
    known = catalogue.get(category) or {}
    item["layer"] = known.get("layer", "accessory")
    item["category_label"] = known.get("label") or category.replace("_", " ").title()
    # A category the user has since deleted leaves its items behind. Say so
    # rather than silently filing them as accessories.
    item["category_known"] = bool(known)
    item["palette"] = db.loads(item.pop("colour_palette", None), [])
    item["seasons"] = db.loads(item.get("seasons"), [])
    item["wind_proof"] = bool(item.get("wind_proof"))
    item["takes_belt"] = bool(item.get("takes_belt", 1))
    item["water_proof"] = bool(item.get("water_proof"))
    item["is_active"] = bool(item.get("is_active", 1))

    threshold = wash_threshold(item, catalogue)
    launderable = threshold > 0
    item["launderable"] = launderable
    item["wash_threshold"] = threshold
    item["wears_left"] = max(0, threshold - int(item.get("wears_since_wash") or 0)) if launderable else None
    item["needs_wash"] = bool(launderable and int(item.get("wears_since_wash") or 0) >= threshold)

    item["image_url"] = photo_url(item.get("image_path"))
    item["thumb_url"] = photo_url(item.get("thumb_path")) or photo_url(item.get("image_path"))
    item["cutout_url"] = photo_url(item.get("cutout_path"))
    item["display_url"] = item["cutout_url"] or item["image_url"]

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
    outfit["is_base"] = bool(outfit.get("is_base"))
    outfit["items"] = items

    # Several items on one of these layers are alternatives, not layers worn
    # together — wearing the outfit picks one. Warmth averages the options per
    # layer instead of summing three t-shirts into a heatwave.
    warmth_layers: dict[str, list[int]] = {}
    for item in items:
        if item.get("layer") in ("bottom", "top", "mid", "outer", "footwear"):
            warmth_layers.setdefault(item["layer"], []).append(int(item.get("warmth") or 0))
    outfit["total_warmth"] = round(sum(
        sum(vals) / len(vals) for vals in warmth_layers.values()))
    outfit["option_layers"] = {layer: len(vals) for layer, vals
                               in warmth_layers.items() if len(vals) > 1}
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
    catalogue = categories.by_key()
    by_id = {r["id"]: item_out(r, catalogue) for r in rows}
    return [by_id[i] for i in ids if i in by_id]
