"""Domain vocabulary: categories, layers, wash defaults, colour naming."""

# Category -> layer slot used by the outfit builder.
CATEGORY_LAYERS = {
    "underwear": "base",
    "sock": "base",
    "top": "top",
    "shirt": "top",
    "bottom": "bottom",
    "dress": "top",
    "pyjamas": "top",
    "mid": "mid",
    "knitwear": "mid",
    "outerwear": "outer",
    "footwear": "footwear",
    "headwear": "accessory",
    "scarf": "accessory",
    "glove": "accessory",
    "belt": "accessory",
    "bag": "accessory",
    "glasses": "accessory",
    "watch": "jewellery",
    "jewellery": "jewellery",
}

CATEGORIES = list(CATEGORY_LAYERS.keys())

# Garments that cover the top and the bottom on their own. The outfit builder
# treats these as a complete layer pair rather than something to wear with
# trousers.
ONE_PIECE_CATEGORIES = {"dress", "pyjamas"}

LAYER_ORDER = ["base", "bottom", "top", "mid", "outer", "footwear", "accessory", "jewellery"]

# Typical insulation by category, used to seed `warmth` before the user tunes it.
DEFAULT_WARMTH = {
    "underwear": 1, "sock": 2, "shirt": 3, "top": 3, "dress": 3, "pyjamas": 4,
    "bottom": 4, "mid": 6, "knitwear": 6, "outerwear": 8, "footwear": 3,
    "headwear": 3, "scarf": 4, "glove": 3, "belt": 0, "bag": 0,
    "glasses": 0, "watch": 0, "jewellery": 0,
}

# Where a newly added item starts on the 1-5 formality scale.
DEFAULT_FORMALITY = {
    "pyjamas": 1, "underwear": 1, "sock": 2, "top": 2, "shirt": 3, "dress": 3,
    "bottom": 2, "mid": 3, "knitwear": 3, "outerwear": 3, "footwear": 3,
    "headwear": 2, "scarf": 3, "glove": 3, "belt": 3, "bag": 3,
    "glasses": 3, "watch": 3, "jewellery": 3,
}

# How a garment sits on you. Only offered for the categories where it is a real
# distinction — a sock has no fit worth recording.
FIT_OPTIONS = {
    "bottom": ["skinny", "regular", "loose", "oversized"],
    "shirt": ["slim", "regular", "loose", "oversized"],
    "top": ["slim", "regular", "loose", "oversized"],
    "dress": ["fitted", "regular", "loose", "oversized"],
    "pyjamas": ["slim", "regular", "loose", "oversized"],
    "knitwear": ["slim", "regular", "loose", "oversized"],
    "mid": ["slim", "regular", "loose", "oversized"],
    "outerwear": ["fitted", "regular", "loose", "oversized"],
}

PATTERNS = ["plain", "stripe", "check", "floral", "print", "logo", "mini logo",
            "knit", "herringbone"]

# Condition of the garment. Kept separate from status, which is about laundry:
# a shirt can be clean and still have a hole in it.
DAMAGE_LEVELS = [
    {"key": "none", "label": "None", "hint": "As good as new"},
    {"key": "mild", "label": "Mild", "hint": "Small mark or loose thread"},
    {"key": "bad", "label": "Bad", "hint": "Hole or stain, needs repair"},
]
DAMAGE_KEYS = [d["key"] for d in DAMAGE_LEVELS]

# Only trousers meaningfully take a belt, so the toggle is offered there. The
# outfit builder uses it to avoid pairing a belt with elasticated joggers.
BELT_CATEGORIES = {"bottom"}

# Free-text fields worth remembering, so typing a brand once is enough.
SUGGESTABLE_FIELDS = ["brand", "material", "subcategory",
                      "colour_primary", "colour_secondary", "name"]

# Suggested tags offered as one-tap chips. Free-text tags still work.
# The occasion words among these do real work: tagging trousers "gym, date"
# tells the outfit builder those are the occasions they belong to.
SUGGESTED_TAGS = ["favourite", "logo", "smart", "comfy", "work", "gym",
                  "going out", "layering", "holiday", "date", "sport",
                  "formal", "lounge", "everyday"]

# Warmth is stored 0-10 because the recommender sums it and compares the total
# against a temperature target. People do not think in eleven grades, so the UI
# offers three, mapped relative to what is typical for the category — a "hot"
# t-shirt and a "hot" overcoat are nothing like the same number.
WARMTH_LEVELS = [
    {"key": "cold", "label": "Cold", "hint": "Keeps you cool", "factor": 0.5},
    {"key": "neutral", "label": "Neutral", "hint": "Typical for the type", "factor": 1.0},
    {"key": "hot", "label": "Hot", "hint": "Keeps you warm", "factor": 1.6},
]

# Formality stays 1-5 so occasions can be matched with some nuance, but the UI
# offers the three steps people actually use. "Informal" sits above casual and
# below formal, as in dress codes, not as a synonym for casual.
FORMALITY_LEVELS = [
    {"key": "casual", "label": "Casual", "hint": "Jeans and trainers", "value": 1},
    {"key": "informal", "label": "Informal", "hint": "Smart but not a suit", "value": 3},
    {"key": "formal", "label": "Formal", "hint": "Suit, tailoring, black tie", "value": 5},
]

SEASONS = ["spring", "summer", "autumn", "winter"]

# Colour vocabulary. The definitions live in `colours` so that naming a pixel,
# canonicalising what someone typed, and sorting a laundry pile all read from
# one table — these names are kept for the modules that already import them.
from .colours import (  # noqa: E402  (placed here to keep the vocabulary together)
    COLOUR_LIST, DARK_COLOURS, LIGHT_COLOURS, METAL_TONES, NEUTRALS, SWATCHES,
)

# (name, rgb) pairs, the shape the reference list has always had.
COLOUR_NAMES = [(name, tuple(int(hexcode[i:i + 2], 16) for i in (1, 3, 5)))
                for name, hexcode in SWATCHES.items()]
