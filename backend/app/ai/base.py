"""Provider contract.

Every method may return None. Callers must treat that as "no AI available" and
fall back to the manual path — the app is fully usable with no provider at all.
"""

from ..constants import (
    BLEACH, CATEGORIES, COLOUR_GROUPS, DRY_CLEAN, IRON_TEMP, SEASONS,
    TUMBLE_DRY, WASH_CYCLES,
)


class Provider:
    name = "none"
    available = False

    def analyse_item(self, image: bytes, mime: str = "image/jpeg") -> dict | None:
        return None

    def read_care_label(self, image: bytes, mime: str = "image/jpeg") -> dict | None:
        return None

    def remove_background(self, image: bytes, mime: str = "image/jpeg") -> bytes | None:
        return None

    def suggest_outfit(self, context: dict) -> dict | None:
        return None


ITEM_PROMPT = f"""You are cataloguing a single garment or accessory for a personal
wardrobe app. Look at the photo and describe only the main item.

Rules:
- category MUST be one of: {', '.join(CATEGORIES)}
- warmth is 1 (barely insulating, e.g. a vest) to 10 (heavy winter coat).
  Judge insulation, not colour. Accessories that add no warmth are 0 or 1.
- formality is 1 (loungewear) to 5 (black tie).
- seasons is any of: {', '.join(SEASONS)}
- colour names should be plain English ("navy", "charcoal", "burgundy").
- name is a short human label, e.g. "Navy merino crew jumper".
- Set wind_proof / water_proof true only when the fabric clearly is.
If the photo is unclear, still give your best estimate and lower `confidence`.
"""

CARE_PROMPT = f"""This photo shows a garment care label. Read the laundry symbols
and any printed text, then report the care instructions.

- wash_temp is degrees Celsius (30, 40, 60, 95). Use null if no wash symbol.
- wash_cycle one of: {', '.join(WASH_CYCLES)}
- tumble_dry one of: {', '.join(TUMBLE_DRY)}
- iron_temp one of: {', '.join(IRON_TEMP)}
- bleach one of: {', '.join(BLEACH)}
- dry_clean one of: {', '.join(DRY_CLEAN)}
- colour_group one of: {', '.join(COLOUR_GROUPS)} (your best guess for sorting laundry)
- raw_symbols: list each symbol you identified in plain words.
Use null for anything you genuinely cannot read. Do not invent instructions.
"""

ITEM_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "name": {"type": "STRING"},
        "category": {"type": "STRING", "enum": CATEGORIES},
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

CARE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "wash_temp": {"type": "INTEGER", "nullable": True},
        "wash_cycle": {"type": "STRING", "enum": WASH_CYCLES, "nullable": True},
        "hand_wash_only": {"type": "BOOLEAN"},
        "do_not_wash": {"type": "BOOLEAN"},
        "tumble_dry": {"type": "STRING", "enum": TUMBLE_DRY, "nullable": True},
        "iron_temp": {"type": "STRING", "enum": IRON_TEMP, "nullable": True},
        "bleach": {"type": "STRING", "enum": BLEACH, "nullable": True},
        "dry_clean": {"type": "STRING", "enum": DRY_CLEAN, "nullable": True},
        "colour_group": {"type": "STRING", "enum": COLOUR_GROUPS, "nullable": True},
        "raw_symbols": {"type": "ARRAY", "items": {"type": "STRING"}},
        "confidence": {"type": "NUMBER"},
    },
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
