"""Provider contract.

Every method may return None. Callers must treat that as "no AI available" and
fall back to the manual path — the app is fully usable with no provider at all.
"""

from ..constants import COLOUR_LIST, SEASONS  # noqa: F401  (SEASONS used in prompt)


class Provider:
    name = "none"
    available = False

    def analyse_item(self, image: bytes, mime: str = "image/jpeg") -> dict | None:
        return None

    def remove_background(self, image: bytes, mime: str = "image/jpeg") -> bytes | None:
        return None

    def suggest_outfit(self, context: dict) -> dict | None:
        return None


_ITEM_PROMPT = """You are cataloguing a single garment or accessory for a personal
wardrobe app. Look at the photo and describe only the main item.

Rules:
- category MUST be one of: {categories}
- warmth is 1 (barely insulating, e.g. a vest) to 10 (heavy winter coat).
  Judge insulation, not colour. Accessories that add no warmth are 0 or 1.
- formality is 1 (loungewear) to 5 (black tie).
- seasons is any of: spring, summer, autumn, winter
- colour_primary and colour_secondary should come from this list where one
  fits: {colours}. Another word is accepted, but a word from the
  list is what sorts the item into a laundry pile and matches it in an outfit.
- Judge the fabric, not the print or the label. Leave colour_secondary empty
  unless a second colour is really part of the garment — a contrast panel or a
  large graphic, not a small logo.
- name is a short human label, e.g. "Navy merino crew jumper".
- Set wind_proof / water_proof true only when the fabric clearly is.
If the photo is unclear, still give your best estimate and lower `confidence`.
"""


def item_prompt() -> str:
    """Built per call, because categories are the user's to change.

    Baking the list in at import time meant a category added this morning was
    invisible to the tagger until the process restarted.
    """
    from .. import categories

    return _ITEM_PROMPT.format(categories=", ".join(categories.keys()),
                              colours=", ".join(COLOUR_LIST))


def item_schema() -> dict:
    from .. import categories

    schema = {**ITEM_SCHEMA, "properties": {**ITEM_SCHEMA["properties"]}}
    schema["properties"]["category"] = {"type": "STRING", "enum": categories.keys()}
    return schema


ITEM_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "name": {"type": "STRING"},
        "category": {"type": "STRING"},
        "subcategory": {"type": "STRING"},
        "brand": {"type": "STRING"},
        "material": {"type": "STRING"},
        "pattern": {"type": "STRING"},
        "colour_primary": {"type": "STRING"},
        "colour_secondary": {"type": "STRING"},
        "warmth": {"type": "INTEGER"},
        "formality": {"type": "INTEGER"},
        "seasons": {"type": "ARRAY", "items": {"type": "STRING", "enum": SEASONS}},
        "wind_proof": {"type": "BOOLEAN"},
        "water_proof": {"type": "BOOLEAN"},
        "confidence": {"type": "NUMBER"},
        "notes": {"type": "STRING"},
    },
    "required": ["name", "category", "colour_primary", "warmth", "formality", "confidence"],
}

OUTFIT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "item_ids": {"type": "ARRAY", "items": {"type": "INTEGER"}},
        "name": {"type": "STRING"},
        "reasoning": {"type": "STRING"},
        "confidence": {"type": "NUMBER"},
    },
    "required": ["item_ids", "reasoning"],
}
