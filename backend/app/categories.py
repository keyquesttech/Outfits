"""The categories a garment can be filed under.

These used to be a dict in `constants`, which meant the only way to stop seeing
"Glasses" in a filter rail was to edit Python. They live in the database now and
belong to the user: the built-in set is seeded on first run, and after that
categories can be added and removed like anything else in the wardrobe.

`layer` is the field that matters. It decides which slot in an outfit a garment
fills, and the builder can only put one garment in each — so a new category has
to name one, and everything else has a sensible default derived from it.
"""

from __future__ import annotations

import re

from . import db
from .constants import (
    BELT_CATEGORIES, CATEGORY_LAYERS, DEFAULT_FORMALITY, DEFAULT_WARMTH,
    FIT_OPTIONS, LAYER_ORDER, ONE_PIECE_CATEGORIES,
)

COLUMNS = ("key", "label", "layer", "warmth", "formality",
           "one_piece", "takes_belt", "fit_options", "is_builtin", "sort_order")

# What a category gets when the user does not say. Picked from the layer,
# because the layer is what a category fundamentally is.
LAYER_DEFAULTS = {
    "base":      {"warmth": 1, "formality": 1, "fit": False},
    "bottom":    {"warmth": 4, "formality": 2, "fit": True},
    "top":       {"warmth": 3, "formality": 2, "fit": True},
    "mid":       {"warmth": 6, "formality": 3, "fit": True},
    "outer":     {"warmth": 8, "formality": 3, "fit": True},
    "footwear":  {"warmth": 3, "formality": 3, "fit": False},
    "accessory": {"warmth": 2, "formality": 3, "fit": False},
    "jewellery": {"warmth": 0, "formality": 3, "fit": False},
}

# Fit words differ by what the garment is: trousers are skinny, coats are fitted.
LAYER_FIT_OPTIONS = {
    "bottom": ["skinny", "regular", "loose", "oversized"],
    "outer": ["fitted", "regular", "loose", "oversized"],
}
DEFAULT_FIT_OPTIONS = ["slim", "regular", "loose", "oversized"]


def slugify(text: str) -> str:
    """A stable key from a label. 'Gym Kit' and 'gym kit' are one category."""
    slug = re.sub(r"[^a-z0-9]+", "_", str(text or "").strip().lower()).strip("_")
    return slug[:40]


def defaults_for(layer: str) -> dict:
    base = LAYER_DEFAULTS.get(layer, LAYER_DEFAULTS["accessory"])
    return {
        "warmth": base["warmth"],
        "formality": base["formality"],
        "fit_options": (LAYER_FIT_OPTIONS.get(layer, DEFAULT_FIT_OPTIONS)
                        if base["fit"] else []),
    }


def _row_out(row: dict) -> dict:
    category = dict(row)
    category["one_piece"] = bool(category.get("one_piece"))
    category["takes_belt"] = bool(category.get("takes_belt"))
    category["is_builtin"] = bool(category.get("is_builtin"))
    category["fit_options"] = db.loads(category.get("fit_options"), [])
    category.pop("wash_after_wears", None)
    return category


def all_categories() -> list[dict]:
    rows = db.query(
        "SELECT * FROM categories ORDER BY sort_order, label COLLATE NOCASE")
    return [_row_out(r) for r in rows]


def by_key() -> dict[str, dict]:
    return {c["key"]: c for c in all_categories()}


def get(key: str) -> dict | None:
    row = db.query_one("SELECT * FROM categories WHERE key = ?", (key,))
    return _row_out(row) if row else None


def keys() -> list[str]:
    return [c["key"] for c in all_categories()]


def counts() -> dict[str, int]:
    """Active items per category, counting the extras an item also counts as.

    The filter rail hides empty categories, and "empty" has to mean the same
    thing there as the filter does — joggers filed as both Bottom and Pyjamas
    keep Pyjamas on screen.
    """
    tally: dict[str, int] = {}
    for row in db.query(
        "SELECT category, COUNT(*) AS count FROM items WHERE is_active = 1 "
        "GROUP BY category"
    ):
        tally[row["category"]] = row["count"]
    for row in db.query(
        "SELECT ic.category AS category, COUNT(*) AS count FROM item_categories ic "
        "JOIN items ON items.id = ic.item_id WHERE items.is_active = 1 "
        "GROUP BY ic.category"
    ):
        tally[row["category"]] = tally.get(row["category"], 0) + row["count"]
    return tally


def usage(key: str) -> dict:
    """How much is riding on this category, for the delete confirmation."""
    primary = db.query_one(
        "SELECT COUNT(*) AS count FROM items WHERE category = ?", (key,)) or {}
    extra = db.query_one(
        "SELECT COUNT(*) AS count FROM item_categories WHERE category = ?", (key,)) or {}
    return {"primary": primary.get("count") or 0, "extra": extra.get("count") or 0}


def layer_of(key: str) -> str:
    return (by_key().get(key) or {}).get("layer", "accessory")


def create(key: str, label: str, layer: str, **overrides) -> dict:
    values = {**defaults_for(layer), "one_piece": False, "takes_belt": layer == "bottom"}
    values.update({k: v for k, v in overrides.items() if v is not None})
    order = db.query_one("SELECT MAX(sort_order) AS top FROM categories") or {}
    db.execute(
        "INSERT INTO categories(key, label, layer, warmth, formality, "
        "one_piece, takes_belt, fit_options, is_builtin, sort_order) "
        "VALUES (?,?,?,?,?,?,?,?,0,?)",
        (key, label, layer, int(values["warmth"]), int(values["formality"]),
         int(bool(values["one_piece"])), int(bool(values["takes_belt"])),
         db.dumps(values["fit_options"]), (order.get("top") or 0) + 1),
    )
    return get(key)


def update(key: str, fields: dict) -> dict | None:
    allowed = {"label", "layer", "warmth", "formality",
               "one_piece", "takes_belt", "fit_options", "sort_order"}
    updates = {}
    for name, value in fields.items():
        if name not in allowed or value is None:
            continue
        if name in ("one_piece", "takes_belt"):
            updates[name] = int(bool(value))
        elif name == "fit_options":
            updates[name] = db.dumps(list(value))
        else:
            updates[name] = value
    if not updates:
        return get(key)
    sets = ", ".join(f"{k} = ?" for k in updates)
    db.execute(f"UPDATE categories SET {sets} WHERE key = ?", (*updates.values(), key))
    return get(key)


def delete(key: str, move_to: str | None = None) -> dict:
    """Remove a category, optionally moving whatever is in it somewhere else.

    Deleting a category that still holds garments would orphan them — they would
    keep a category name nothing recognises, so they would lose their layer and
    quietly stop appearing in outfits. Either the items move, or the delete is
    refused.
    """
    counts = usage(key)
    if (counts["primary"] or counts["extra"]) and not move_to:
        return {"deleted": False, **counts}
    if move_to:
        db.execute("UPDATE items SET category = ?, updated_at = datetime('now') "
                   "WHERE category = ?", (move_to, key))
        # An item can already be filed under the destination, so move what does
        # not collide and drop the rest rather than failing on the primary key.
        db.execute(
            "UPDATE OR IGNORE item_categories SET category = ? WHERE category = ?",
            (move_to, key))
        db.execute("DELETE FROM item_categories WHERE category = ?", (key,))
        # A move can leave an item listing its own primary category as an extra.
        db.execute(
            "DELETE FROM item_categories WHERE category = "
            "(SELECT category FROM items WHERE items.id = item_categories.item_id)")
    db.execute("DELETE FROM categories WHERE key = ?", (key,))
    return {"deleted": True, "moved_to": move_to, **counts}


def seed(conn) -> int:
    """Fill the table from the built-in set, once.

    Runs against the raw connection during schema setup, before the request
    helpers are usable.
    """
    existing = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
    if existing:
        return 0
    rows = []
    for order, (key, layer) in enumerate(CATEGORY_LAYERS.items()):
        rows.append((
            key, key.replace("_", " ").title(), layer,
            DEFAULT_WARMTH.get(key, 3), DEFAULT_FORMALITY.get(key, 3),
            int(key in ONE_PIECE_CATEGORIES), int(key in BELT_CATEGORIES),
            db.dumps(FIT_OPTIONS.get(key, [])), 1, order,
        ))
    conn.executemany(
        "INSERT INTO categories(key, label, layer, warmth, formality, "
        "one_piece, takes_belt, fit_options, is_builtin, "
        "sort_order) VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    return len(rows)


def layers() -> list[dict]:
    """The fixed slots a category can occupy, with what each one means."""
    described = {
        "base": "Worn underneath — socks, underwear",
        "bottom": "Trousers, skirts, shorts",
        "top": "Shirts, t-shirts, dresses",
        "mid": "Jumpers and cardigans over a top",
        "outer": "Coats and jackets, worn last",
        "footwear": "Shoes and boots",
        "accessory": "Hats, scarves, belts, bags",
        "jewellery": "Metal, not a clashing colour",
    }
    return [{"key": k, "label": k.title(), "hint": described.get(k, "")}
            for k in LAYER_ORDER]
