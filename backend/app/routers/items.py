from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from .. import config, db, images, jobs, wash
from ..constants import (
    BELT_CATEGORIES, BLEACH, CATEGORIES, CATEGORY_LAYERS, COLOUR_GROUPS,
    DAMAGE_KEYS, DAMAGE_LEVELS, DEFAULT_FORMALITY, DEFAULT_WARMTH,
    DEFAULT_WASH_AFTER_WEARS, DRY_CLEAN, FIT_OPTIONS, FORMALITY_LEVELS, IRON_TEMP,
    LAYER_ORDER, NO_WASH_CATEGORIES, PATTERNS, SEASONS, STATUSES, SUGGESTABLE_FIELDS,
    SUGGESTED_TAGS, TUMBLE_DRY, WARMTH_LEVELS, WASH_CYCLES,
)
from ..models import CareIn, ItemIn, ItemPatch, StatusIn
from ..serializers import care_out, item_out

router = APIRouter(prefix="/api", tags=["items"])

ITEM_COLUMNS = {
    "name", "category", "subcategory", "brand", "material", "pattern",
    "colour_primary", "colour_secondary", "warmth", "formality", "seasons",
    "wind_proof", "water_proof", "fit", "damage", "takes_belt",
    "wash_after_wears", "status", "notes", "is_active", "colour_palette",
    "image_path", "thumb_path", "cutout_path",
}


@router.get("/meta")
def meta():
    return {
        "categories": CATEGORIES,
        "category_layers": CATEGORY_LAYERS,
        "layers": LAYER_ORDER,
        "statuses": STATUSES,
        "seasons": SEASONS,
        "wash_cycles": WASH_CYCLES,
        "tumble_dry": TUMBLE_DRY,
        "iron_temp": IRON_TEMP,
        "bleach": BLEACH,
        "dry_clean": DRY_CLEAN,
        "colour_groups": COLOUR_GROUPS,
        "no_wash_categories": sorted(NO_WASH_CATEGORIES),
        "default_wash_after_wears": DEFAULT_WASH_AFTER_WEARS,
        "default_warmth": DEFAULT_WARMTH,
        "default_formality": DEFAULT_FORMALITY,
        "patterns": PATTERNS,
        "damage_levels": DAMAGE_LEVELS,
        "belt_categories": sorted(BELT_CATEGORIES),
        "fit_options": FIT_OPTIONS,
        "suggested_tags": SUGGESTED_TAGS,
        "warmth_levels": WARMTH_LEVELS,
        "formality_levels": FORMALITY_LEVELS,
    }


def _set_tags(item_id: int, tags: list[str] | None) -> None:
    if tags is None:
        return
    db.execute("DELETE FROM item_tags WHERE item_id = ?", (item_id,))
    for name in {t.strip().lower() for t in tags if t.strip()}:
        db.execute("INSERT OR IGNORE INTO tags(name) VALUES (?)", (name,))
        row = db.query_one("SELECT id FROM tags WHERE name = ?", (name,))
        if row:
            db.execute("INSERT OR IGNORE INTO item_tags(item_id, tag_id) VALUES (?,?)",
                       (item_id, row["id"]))


def _set_categories(item_id: int, primary: str, extras: list[str] | None) -> None:
    """Store the extra categories an item also counts as.

    The primary is never duplicated in here; it lives on items.category and is
    what decides the item's layer and defaults.
    """
    if extras is None:
        return
    db.execute("DELETE FROM item_categories WHERE item_id = ?", (item_id,))
    wanted = {c for c in extras if c in CATEGORIES and c != primary}
    db.executemany(
        "INSERT OR IGNORE INTO item_categories(item_id, category) VALUES (?,?)",
        [(item_id, c) for c in sorted(wanted)],
    )


def _categories_for(item_id: int, primary: str) -> list[str]:
    extra = [r["category"] for r in db.query(
        "SELECT category FROM item_categories WHERE item_id = ? ORDER BY category", (item_id,)
    )]
    return [primary] + [c for c in extra if c != primary]


def _tags_for(item_id: int) -> list[str]:
    return [r["name"] for r in db.query(
        "SELECT tags.name FROM tags JOIN item_tags ON tags.id = item_tags.tag_id "
        "WHERE item_tags.item_id = ? ORDER BY tags.name", (item_id,)
    )]


def _hydrate(row: dict) -> dict:
    item = item_out(row)
    item["categories"] = _categories_for(item["id"], item["category"])
    item["extra_categories"] = item["categories"][1:]
    item["tags"] = _tags_for(item["id"])
    item["care"] = care_out(db.query_one(
        "SELECT * FROM care_instructions WHERE item_id = ?", (item["id"],)
    ))
    return item


@router.get("/items")
def list_items(
    category: str | None = None,
    status: str | None = None,
    layer: str | None = None,
    colour: str | None = None,
    season: str | None = None,
    tag: str | None = None,
    q: str | None = None,
    include_inactive: bool = False,
    needs_wash: bool | None = None,
    sort: str = Query("recent", pattern="^(recent|name|worn|least_worn)$"),
    limit: int = Query(500, ge=1, le=2000),
):
    sql = "SELECT items.* FROM items"
    params: list = []
    where: list[str] = []

    if tag:
        sql += (" JOIN item_tags ON items.id = item_tags.item_id"
                " JOIN tags ON tags.id = item_tags.tag_id")
        where.append("tags.name = ?")
        params.append(tag.lower())
    if not include_inactive:
        where.append("items.is_active = 1")
    if category:
        # Match the primary or any extra category, so a pair of joggers filed as
        # both bottom and pyjamas turns up under either.
        where.append(
            "(items.category = ? OR EXISTS (SELECT 1 FROM item_categories ic "
            "WHERE ic.item_id = items.id AND ic.category = ?))"
        )
        params += [category, category]
    if status:
        where.append("items.status = ?")
        params.append(status)
    if colour:
        where.append("LOWER(items.colour_primary) = ?")
        params.append(colour.lower())
    if season:
        where.append("items.seasons LIKE ?")
        params.append(f"%{season}%")
    if q:
        where.append("(items.name LIKE ? OR items.brand LIKE ? OR items.notes LIKE ? "
                     "OR items.subcategory LIKE ? OR items.material LIKE ?)")
        params += [f"%{q}%"] * 5
    if where:
        sql += " WHERE " + " AND ".join(where)

    order = {
        "recent": "items.id DESC",
        "name": "items.name COLLATE NOCASE",
        "worn": "items.total_wears DESC",
        "least_worn": "items.total_wears ASC",
    }[sort]
    sql += f" ORDER BY {order} LIMIT ?"
    params.append(limit)

    items = []
    for r in db.query(sql, tuple(params)):
        item = item_out(r)
        item["categories"] = _categories_for(item["id"], item["category"])
        item["extra_categories"] = item["categories"][1:]
        items.append(item)
    if layer:
        items = [i for i in items if i["layer"] == layer]
    if needs_wash is not None:
        items = [i for i in items if i["needs_wash"] == needs_wash]
    return {"items": items, "count": len(items)}


@router.get("/items/{item_id}")
def get_item(item_id: int):
    row = db.query_one("SELECT * FROM items WHERE id = ?", (item_id,))
    if not row:
        raise HTTPException(404, "Item not found")
    item = _hydrate(row)
    item["worn_history"] = db.query(
        "SELECT wear_log.* FROM wear_log JOIN wear_log_items "
        "ON wear_log.id = wear_log_items.wear_log_id WHERE wear_log_items.item_id = ? "
        "ORDER BY worn_on DESC LIMIT 30", (item_id,)
    )
    item["wash_history"] = db.query(
        "SELECT wash_batches.* FROM wash_batches JOIN wash_batch_items "
        "ON wash_batches.id = wash_batch_items.batch_id WHERE wash_batch_items.item_id = ? "
        "ORDER BY washed_on DESC LIMIT 30", (item_id,)
    )
    return item


def _default_wash(category: str, explicit: int | None) -> int | None:
    if explicit is not None:
        return explicit
    if category in NO_WASH_CATEGORIES:
        return 0
    return DEFAULT_WASH_AFTER_WEARS.get(category)


@router.post("/items", status_code=201)
def create_item(payload: ItemIn):
    if payload.category not in CATEGORIES:
        raise HTTPException(400, f"Unknown category: {payload.category}")
    item_id = db.execute(
        "INSERT INTO items(name, category, subcategory, brand, material, pattern, fit, "
        "damage, takes_belt, colour_primary, colour_secondary, warmth, formality, seasons, "
        "wind_proof, water_proof, wash_after_wears, notes) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            payload.name, payload.category, payload.subcategory, payload.brand,
            payload.material, payload.pattern, payload.fit,
            payload.damage if payload.damage in DAMAGE_KEYS else "none",
            int(payload.takes_belt), payload.colour_primary,
            payload.colour_secondary, payload.warmth, payload.formality,
            db.dumps(payload.seasons or []), int(payload.wind_proof),
            int(payload.water_proof),
            _default_wash(payload.category, payload.wash_after_wears),
            payload.notes,
        ),
    )
    _set_categories(item_id, payload.category, payload.categories)
    _set_tags(item_id, payload.tags)
    return _hydrate(db.query_one("SELECT * FROM items WHERE id = ?", (item_id,)))


@router.post("/items/upload", status_code=201)
async def upload_item(
    file: UploadFile = File(...),
    name: str = Form("Untitled item"),
    category: str = Form("top"),
    analyse: bool = Form(True),
    cutout: bool = Form(False),
):
    data = await file.read()
    if len(data) > config.UPLOAD_MAX_BYTES:
        raise HTTPException(413, "Photo is larger than 25 MB")
    try:
        saved = images.save_upload(data, file.filename or "")
    except Exception as exc:
        raise HTTPException(400, f"Could not read that image: {exc}") from exc

    palette = saved["palette"]
    primary = palette[0]["name"] if palette else None
    secondary = palette[1]["name"] if len(palette) > 1 else None

    item_id = db.execute(
        "INSERT INTO items(name, category, colour_primary, colour_secondary, "
        "colour_palette, warmth, formality, image_path, thumb_path, wash_after_wears, seasons) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            name, category, primary, secondary, db.dumps(palette),
            DEFAULT_WARMTH.get(category, 5), DEFAULT_FORMALITY.get(category, 3),
            saved["image_path"], saved["thumb_path"],
            _default_wash(category, None), db.dumps([]),
        ),
    )

    queued = []
    provider_ready = db.get_setting("ai_provider", "none") != "none"
    if analyse and provider_ready:
        queued.append(jobs.enqueue("analyse_item", item_id))
    if cutout and provider_ready:
        queued.append(jobs.enqueue("cutout", item_id))

    item = _hydrate(db.query_one("SELECT * FROM items WHERE id = ?", (item_id,)))
    item["queued_jobs"] = queued
    item["ai_enabled"] = provider_ready
    return item


@router.post("/items/{item_id}/photo")
async def replace_photo(item_id: int, file: UploadFile = File(...), analyse: bool = Form(False)):
    if not db.query_one("SELECT id FROM items WHERE id = ?", (item_id,)):
        raise HTTPException(404, "Item not found")
    data = await file.read()
    saved = images.save_upload(data, file.filename or "")
    db.execute(
        "UPDATE items SET image_path = ?, thumb_path = ?, colour_palette = ?, "
        "cutout_path = NULL, updated_at = datetime('now') WHERE id = ?",
        (saved["image_path"], saved["thumb_path"], db.dumps(saved["palette"]), item_id),
    )
    if analyse and db.get_setting("ai_provider", "none") != "none":
        jobs.enqueue("analyse_item", item_id)
    return _hydrate(db.query_one("SELECT * FROM items WHERE id = ?", (item_id,)))


@router.patch("/items/{item_id}")
def update_item(item_id: int, payload: ItemPatch):
    row = db.query_one("SELECT * FROM items WHERE id = ?", (item_id,))
    if not row:
        raise HTTPException(404, "Item not found")

    fields = payload.model_dump(exclude_unset=True)
    tags = fields.pop("tags", None)
    extra_categories = fields.pop("categories", None)
    updates: dict = {}
    for key, value in fields.items():
        if key not in ITEM_COLUMNS:
            continue
        if key == "seasons":
            updates[key] = db.dumps(value or [])
        elif key in ("wind_proof", "water_proof", "is_active", "takes_belt"):
            updates[key] = int(bool(value))
        else:
            updates[key] = value

    if "category" in updates and updates["category"] not in CATEGORIES:
        raise HTTPException(400, f"Unknown category: {updates['category']}")
    if "status" in updates and updates["status"] not in STATUSES:
        raise HTTPException(400, f"Unknown status: {updates['status']}")
    if updates.get("damage") and updates["damage"] not in DAMAGE_KEYS:
        raise HTTPException(400, f"Unknown damage level: {updates['damage']}")

    if updates:
        sets = ", ".join(f"{k} = ?" for k in updates)
        db.execute(f"UPDATE items SET {sets}, updated_at = datetime('now') WHERE id = ?",
                   (*updates.values(), item_id))
    _set_tags(item_id, tags)
    _set_categories(item_id, updates.get("category", row["category"]), extra_categories)
    if {"category", "wash_after_wears"} & set(updates):
        wash.refresh_status(item_id)
    return _hydrate(db.query_one("SELECT * FROM items WHERE id = ?", (item_id,)))


@router.post("/items/{item_id}/status")
def change_status(item_id: int, payload: StatusIn):
    if payload.status not in STATUSES:
        raise HTTPException(400, f"Unknown status: {payload.status}")
    result = wash.set_status(item_id, payload.status)
    if not result:
        raise HTTPException(404, "Item not found")
    return result


@router.delete("/items/{item_id}")
def delete_item(item_id: int, hard: bool = False):
    row = db.query_one("SELECT * FROM items WHERE id = ?", (item_id,))
    if not row:
        raise HTTPException(404, "Item not found")
    if hard:
        for key in ("image_path", "thumb_path", "cutout_path"):
            rel = row.get(key)
            if rel:
                (config.PHOTO_DIR / rel).unlink(missing_ok=True)
        db.execute("DELETE FROM items WHERE id = ?", (item_id,))
        return {"deleted": item_id, "hard": True}
    db.execute("UPDATE items SET is_active = 0, updated_at = datetime('now') WHERE id = ?",
               (item_id,))
    return {"deleted": item_id, "hard": False}


@router.get("/items/{item_id}/care")
def get_care(item_id: int):
    return care_out(db.query_one("SELECT * FROM care_instructions WHERE item_id = ?", (item_id,)))


@router.put("/items/{item_id}/care")
def put_care(item_id: int, payload: CareIn):
    if not db.query_one("SELECT id FROM items WHERE id = ?", (item_id,)):
        raise HTTPException(404, "Item not found")
    jobs._apply_care(item_id, {**payload.model_dump(), "raw_symbols": []}, "manual")
    if payload.notes:
        db.execute("UPDATE care_instructions SET notes = ? WHERE item_id = ?",
                   (payload.notes, item_id))
    return care_out(db.query_one("SELECT * FROM care_instructions WHERE item_id = ?", (item_id,)))


@router.post("/items/{item_id}/care-label")
async def read_care_label(item_id: int, file: UploadFile = File(...)):
    """Photograph the care label; AI turns the symbols into wash settings."""
    if not db.query_one("SELECT id FROM items WHERE id = ?", (item_id,)):
        raise HTTPException(404, "Item not found")
    if db.get_setting("ai_provider", "none") == "none":
        raise HTTPException(400, "Reading care labels needs an AI provider. "
                                 "Enter the care details by hand instead.")
    data = await file.read()
    saved = images.save_upload(data, file.filename or "")
    job_id = jobs.enqueue("care_label", item_id, {"image_path": saved["image_path"]})
    return {"job_id": job_id, "status": "queued"}


@router.post("/items/{item_id}/analyse")
def analyse(item_id: int, kind: str = Query("analyse_item", pattern="^(analyse_item|cutout)$")):
    if not db.query_one("SELECT id FROM items WHERE id = ?", (item_id,)):
        raise HTTPException(404, "Item not found")
    if db.get_setting("ai_provider", "none") == "none":
        raise HTTPException(400, "No AI provider configured")
    return {"job_id": jobs.enqueue(kind, item_id), "status": "queued"}


@router.get("/field-values")
def field_values(limit: int = Query(40, ge=1, le=200)):
    """Distinct values already used in each free-text field, commonest first.

    Feeds the type-ahead on the item form so a brand only has to be typed once.
    """
    out: dict[str, list[str]] = {}
    for field in SUGGESTABLE_FIELDS:
        rows = db.query(
            f"SELECT {field} AS value, COUNT(*) AS uses FROM items "
            f"WHERE {field} IS NOT NULL AND TRIM({field}) != '' "
            "GROUP BY LOWER(TRIM(value)) ORDER BY uses DESC, value COLLATE NOCASE LIMIT ?",
            (limit,),
        )
        out[field] = [r["value"] for r in rows]
    return out


@router.get("/tags")
def list_tags():
    return db.query(
        "SELECT tags.name, COUNT(item_tags.item_id) AS count FROM tags "
        "LEFT JOIN item_tags ON tags.id = item_tags.tag_id GROUP BY tags.id "
        "ORDER BY count DESC, tags.name"
    )
