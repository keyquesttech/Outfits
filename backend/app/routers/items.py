import re

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from .. import categories, colours, config, db, images, jobs, wash
from ..ai import get_provider
from ..constants import (
    BLEACH, COLOUR_GROUPS, DAMAGE_KEYS, DAMAGE_LEVELS, DRY_CLEAN,
    FORMALITY_LEVELS, IRON_TEMP, LAYER_ORDER, PATTERNS, SEASONS, STATUSES,
    SUGGESTABLE_FIELDS, SUGGESTED_TAGS, TUMBLE_DRY, WARMTH_LEVELS, WASH_CYCLES,
)
from ..models import CareIn, CategoryIn, CategoryPatch, ItemIn, ItemPatch, StatusIn
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
    """Everything the UI needs to render a form, in one call.

    The category-shaped fields are derived from the table rather than listed
    separately, so adding a category cannot half-appear: it arrives with its
    layer, its defaults and its fit words at the same moment.
    """
    catalogue = categories.all_categories()
    in_use = categories.counts()
    # Whether AI is usable at all, so the UI can leave out the controls that
    # only do something with a key behind them rather than offering a button
    # whose whole result is "set up AI".
    provider = get_provider()
    return {
        "ai": {"provider": provider.name, "available": provider.available},
        "categories": [c["key"] for c in catalogue],
        "category_list": [{**c, "count": in_use.get(c["key"], 0)} for c in catalogue],
        "category_layers": {c["key"]: c["layer"] for c in catalogue},
        "category_labels": {c["key"]: c["label"] for c in catalogue},
        "category_counts": in_use,
        "layers": LAYER_ORDER,
        "layer_options": categories.layers(),
        "statuses": STATUSES,
        "seasons": SEASONS,
        "wash_cycles": WASH_CYCLES,
        "tumble_dry": TUMBLE_DRY,
        "iron_temp": IRON_TEMP,
        "bleach": BLEACH,
        "dry_clean": DRY_CLEAN,
        "colour_groups": COLOUR_GROUPS,
        "colours": colours.palette_options(),
        "colour_lookup": colours.lookup_table(),
        "colour_blanks": sorted(colours.BLANKS),
        "no_wash_categories": sorted(c["key"] for c in catalogue if not c["launderable"]),
        "default_wash_after_wears": {c["key"]: c["wash_after_wears"] for c in catalogue},
        "default_warmth": {c["key"]: c["warmth"] for c in catalogue},
        "default_formality": {c["key"]: c["formality"] for c in catalogue},
        "patterns": PATTERNS,
        "damage_levels": DAMAGE_LEVELS,
        "belt_categories": sorted(c["key"] for c in catalogue if c["takes_belt"]),
        "fit_options": {c["key"]: c["fit_options"] for c in catalogue if c["fit_options"]},
        "suggested_tags": SUGGESTED_TAGS,
        "warmth_levels": WARMTH_LEVELS,
        "formality_levels": FORMALITY_LEVELS,
    }


# Tokens that only ever came from a camera or an export, never from a person.
_FILENAME_NOISE = {
    "img", "dsc", "dscn", "dscf", "pxl", "mvimg", "photo", "photos", "image",
    "images", "picture", "pic", "screenshot", "screen", "shot", "capture",
    "untitled", "unnamed", "download", "downloads", "copy", "final", "edit",
    "edited", "new", "temp", "tmp", "gemini", "generated", "chatgpt",
    "whatsapp", "signal", "received", "snapchat", "export", "render", "file",
    "camera", "live", "resized", "compressed", "output",
    # The browser strips the extension before uploading; a direct API call does not.
    "jpg", "jpeg", "png", "heic", "heif", "webp", "gif", "bmp", "tif", "tiff",
}


# A camera prefix followed by a frame number: IMG4821, DSC00123, PXL20230101.
_SERIAL = re.compile(r"^[a-z]{1,5}\d{3,}[a-z0-9]*$")


def _is_noise(token: str) -> bool:
    lowered = token.lower()
    if lowered in _FILENAME_NOISE:
        return True
    # Short numbers are part of the name — Levi's 501, 20-eye boots — but a
    # four-digit run is a date or a frame number.
    if lowered.isdigit():
        return len(lowered) >= 4
    if _SERIAL.match(lowered):
        return True
    if len(lowered) >= 8 and all(c in "0123456789abcdef" for c in lowered):
        return True
    # "x9abi9x9abi9x9ab" and "20240817-142233" — long, and mixing letters with
    # digits the way a serial number does and a garment name does not.
    return len(lowered) >= 10 and any(c.isdigit() for c in lowered)


def item_display_name(raw: str | None, category: str, colour: str | None) -> str:
    """A name worth showing, from whatever the phone called the file.

    Uploads are named after the file, which is how "Gemini_Generated_Image_
    x9abi9x9abi9x9ab" and "IMG_4821" ended up as garments in the wardrobe. When
    nothing human survives, the colour and the category make a better first
    label than "Untitled item" — and it is still editable.
    """
    words = [w for w in re.split(r"[\s_\-.]+", str(raw or "").strip()) if w]
    kept = [w for w in words if not _is_noise(w)]
    # "Screenshot 2024-01-02 at 10.11.12" leaves "at" behind. One stray joining
    # word is not a name, so require something with substance in it.
    if any(len(w) >= 3 and any(c.isalpha() for c in w) for w in kept):
        return " ".join(kept)[:120]
    name = colours.canonical(colour)
    if name:
        return f"{name.title()} {category.replace('_', ' ').title()}"
    return "Untitled item"


def _tidy_colours(fields: dict, current: dict | None = None) -> None:
    """Store colours in the app's own vocabulary, in place.

    Everything downstream — laundry piles, outfit harmony, the colour filter,
    the analytics chart — looks colours up by name, and every one of those
    lookups missed for "Gray", "Dark Red" and "N/A". Normalising once on the way
    in means they cannot miss. A word the vocabulary does not know is kept as
    typed rather than thrown away; the form marks it so it can be corrected.

    `current` is the row being patched, so a partial update can still tell that
    the primary it is setting now matches the secondary already stored.
    """
    current = current or {}
    for field in ("colour_primary", "colour_secondary"):
        if field in fields:
            fields[field] = colours.normalise(fields[field])
    primary = fields.get("colour_primary", current.get("colour_primary"))
    secondary = fields.get("colour_secondary", current.get("colour_secondary"))
    if primary and secondary and colours.same_shade(primary, secondary):
        fields["colour_secondary"] = None


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
    known = set(categories.keys())
    wanted = {c for c in extras if c in known and c != primary}
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
        # Filter on the canonical name so "Gray" and "grey" are one filter, and
        # match the secondary too — a black shirt with a white print is white
        # enough to want when you are looking for white.
        wanted = colours.canonical(colour) or colour.lower()
        where.append("(LOWER(items.colour_primary) = ? OR LOWER(items.colour_secondary) = ?)")
        params += [wanted, wanted]
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
    known = categories.get(category)
    return int(known["wash_after_wears"]) if known else None


@router.post("/items", status_code=201)
def create_item(payload: ItemIn):
    if not categories.get(payload.category):
        raise HTTPException(400, f"Unknown category: {payload.category}")
    tidy = {"colour_primary": payload.colour_primary,
            "colour_secondary": payload.colour_secondary}
    _tidy_colours(tidy)
    item_id = db.execute(
        "INSERT INTO items(name, category, subcategory, brand, material, pattern, fit, "
        "damage, takes_belt, colour_primary, colour_secondary, warmth, formality, seasons, "
        "wind_proof, water_proof, wash_after_wears, notes) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            payload.name, payload.category, payload.subcategory, payload.brand,
            payload.material, payload.pattern, payload.fit,
            payload.damage if payload.damage in DAMAGE_KEYS else "none",
            int(payload.takes_belt), tidy["colour_primary"],
            tidy["colour_secondary"], payload.warmth, payload.formality,
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
    # The default here is a string, not a live lookup, so it can name a category
    # that has since been removed. Fall back to whatever exists rather than
    # writing an item nothing can file.
    if not categories.get(category):
        available = categories.keys()
        if not available:
            raise HTTPException(400, "There are no categories to file this under")
        category = available[0]
    try:
        saved = images.save_upload(data, file.filename or "")
    except Exception as exc:
        raise HTTPException(400, f"Could not read that image: {exc}") from exc

    palette = saved["palette"]
    primary, secondary = images.suggest_colours(palette)
    name = item_display_name(name, category, primary)
    defaults = categories.get(category) or {}

    item_id = db.execute(
        "INSERT INTO items(name, category, colour_primary, colour_secondary, "
        "colour_palette, warmth, formality, image_path, thumb_path, wash_after_wears, seasons) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            name, category, primary, secondary, db.dumps(palette),
            defaults.get("warmth", 5), defaults.get("formality", 3),
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
    if len(data) > config.UPLOAD_MAX_BYTES:
        raise HTTPException(413, "Photo is larger than 25 MB")
    # The default here is a string, not a live lookup, so it can name a category
    # that has since been removed. Fall back to whatever exists rather than
    # writing an item nothing can file.
    if not categories.get(category):
        available = categories.keys()
        if not available:
            raise HTTPException(400, "There are no categories to file this under")
        category = available[0]
    try:
        saved = images.save_upload(data, file.filename or "")
    except Exception as exc:
        raise HTTPException(400, f"Could not read that image: {exc}") from exc
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
    _tidy_colours(fields, row)
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

    if "category" in updates and not categories.get(updates["category"]):
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


def _rescan(row: dict, overwrite: bool) -> dict | None:
    """Read the palette off an item's photo again and, carefully, its colours."""
    blob = images.photo_bytes(row.get("image_path") or "")
    if not blob:
        return None
    try:
        picture = images.open_photo(blob)
    except Exception:
        return None

    palette = images.extract_palette(picture)
    primary, secondary = images.suggest_colours(palette)
    updates = {"colour_palette": db.dumps(palette)}

    # Without `overwrite` this only fills what is not already a colour the app
    # recognises, so a name chosen by hand is never quietly replaced by a guess.
    if overwrite or not colours.canonical(row.get("colour_primary")):
        updates["colour_primary"] = primary
    if overwrite or not colours.canonical(row.get("colour_secondary")):
        updates["colour_secondary"] = secondary
    if colours.same_shade(updates.get("colour_primary", row.get("colour_primary")),
                          updates.get("colour_secondary", row.get("colour_secondary"))):
        updates["colour_secondary"] = None

    sets = ", ".join(f"{k} = ?" for k in updates)
    db.execute(f"UPDATE items SET {sets}, updated_at = datetime('now') WHERE id = ?",
               (*updates.values(), row["id"]))
    return {
        "id": row["id"], "name": row.get("name"),
        "was": row.get("colour_primary"),
        "now": updates.get("colour_primary", row.get("colour_primary")),
        "palette": palette,
    }


@router.post("/colours/rescan")
def rescan_colours(overwrite: bool = False, limit: int = Query(400, ge=1, le=2000)):
    """Re-read every photo with the current colour engine.

    Worth having as a button rather than a migration: the palette stored against
    an item was produced by whatever version of the extractor was running the
    day it was uploaded, and re-reading a few hundred photos takes seconds.
    """
    rows = db.query("SELECT * FROM items WHERE image_path IS NOT NULL "
                    "ORDER BY id LIMIT ?", (limit,))
    changed, unreadable = [], 0
    for row in rows:
        result = _rescan(row, overwrite)
        if result is None:
            unreadable += 1
        elif str(result["was"] or "").lower() != str(result["now"] or "").lower():
            changed.append({k: result[k] for k in ("id", "name", "was", "now")})
    return {"scanned": len(rows), "changed": changed,
            "unreadable": unreadable, "overwrite": overwrite}


@router.post("/items/{item_id}/rescan-colours")
def rescan_item_colours(item_id: int, overwrite: bool = True):
    row = db.query_one("SELECT * FROM items WHERE id = ?", (item_id,))
    if not row:
        raise HTTPException(404, "Item not found")
    if not _rescan(row, overwrite):
        raise HTTPException(400, "That item has no readable photo")
    return _hydrate(db.query_one("SELECT * FROM items WHERE id = ?", (item_id,)))


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


@router.get("/categories")
def list_categories():
    """Every category, with how many garments are in it.

    The count is what the wardrobe filter hides an empty category on, and what
    the delete confirmation needs, so both read the same number.
    """
    in_use = categories.counts()
    return {"categories": [{**c, "count": in_use.get(c["key"], 0)}
                           for c in categories.all_categories()],
            "layers": categories.layers()}


@router.post("/categories", status_code=201)
def create_category(payload: CategoryIn):
    label = " ".join(str(payload.label or "").split())
    if not label:
        raise HTTPException(400, "A category needs a name")
    if payload.layer not in LAYER_ORDER:
        raise HTTPException(400, f"Unknown layer: {payload.layer}")
    key = categories.slugify(label)
    if not key:
        raise HTTPException(400, "That name has no letters or numbers in it")
    if categories.get(key):
        raise HTTPException(409, f"There is already a category called {label}")
    return categories.create(
        key, label, payload.layer,
        warmth=payload.warmth, formality=payload.formality,
        wash_after_wears=payload.wash_after_wears,
        one_piece=payload.one_piece, takes_belt=payload.takes_belt,
        fit_options=payload.fit_options,
    )


@router.patch("/categories/{key}")
def update_category(key: str, payload: CategoryPatch):
    if not categories.get(key):
        raise HTTPException(404, "Category not found")
    fields = payload.model_dump(exclude_unset=True)
    if fields.get("layer") and fields["layer"] not in LAYER_ORDER:
        raise HTTPException(400, f"Unknown layer: {fields['layer']}")
    if "label" in fields:
        fields["label"] = " ".join(str(fields["label"] or "").split())
        if not fields["label"]:
            raise HTTPException(400, "A category needs a name")
    return categories.update(key, fields)


@router.delete("/categories/{key}")
def delete_category(key: str, move_to: str | None = None):
    """Remove a category. Anything in it has to go somewhere first.

    Deleting one that still holds garments would leave them pointing at a name
    nothing recognises — no layer, so no outfits, no wash threshold. Either name
    a category to move them to, or the request comes back saying how many are in
    the way.
    """
    if not categories.get(key):
        raise HTTPException(404, "Category not found")
    if len(categories.keys()) <= 1:
        raise HTTPException(409, "This is the only category left. Add another "
                                 "before removing it, or nothing can be filed anywhere.")
    if move_to:
        if move_to == key:
            raise HTTPException(400, "Move the items somewhere other than here")
        if not categories.get(move_to):
            raise HTTPException(400, f"Unknown category: {move_to}")
    result = categories.delete(key, move_to)
    if not result["deleted"]:
        raise HTTPException(409, {
            "message": f"{result['primary']} item(s) are filed under this. "
                       "Move them to another category first.",
            **result,
        })
    return result


@router.get("/tags")
def list_tags():
    return db.query(
        "SELECT tags.name, COUNT(item_tags.item_id) AS count FROM tags "
        "LEFT JOIN item_tags ON tags.id = item_tags.tag_id GROUP BY tags.id "
        "ORDER BY count DESC, tags.name"
    )
