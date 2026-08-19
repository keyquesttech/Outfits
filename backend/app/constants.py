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

# Categories that are never laundered — jewellery, watches, glasses, bags.
NO_WASH_CATEGORIES = {"jewellery", "watch", "glasses", "bag"}

# Wears before an item needs laundering. Overridable per item.
DEFAULT_WASH_AFTER_WEARS = {
    "underwear": 1,
    "sock": 1,
    "shirt": 2,
    "top": 2,
    "dress": 2,
    "pyjamas": 4,
    "bottom": 4,
    "mid": 5,
    "knitwear": 5,
    "outerwear": 25,
    "footwear": 30,
    "headwear": 10,
    "scarf": 8,
    "glove": 8,
    "belt": 0,
    "bag": 0,
    "glasses": 0,
    "watch": 0,
    "jewellery": 0,
}

# Typical insulation by category, used to seed `warmth` before the user tunes it.
DEFAULT_WARMTH = {
    "underwear": 1, "sock": 2, "shirt": 3, "top": 3, "dress": 3, "pyjamas": 4,
    "bottom": 4, "mid": 6, "knitwear": 6, "outerwear": 8, "footwear": 3,
    "headwear": 3, "scarf": 4, "glove": 3, "belt": 0, "bag": 0,
    "glasses": 0, "watch": 0, "jewellery": 0,
}

STATUSES = ["clean", "worn", "needs_wash", "airing", "in_wash"]

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

PATTERNS = ["plain", "stripe", "check", "floral", "print", "logo", "knit", "herringbone"]

# Suggested tags offered as one-tap chips. Free-text tags still work.
SUGGESTED_TAGS = ["favourite", "logo", "smart", "comfy", "work", "gym",
                  "going out", "layering", "holiday"]

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

WASH_CYCLES = ["normal", "synthetics", "delicate", "wool", "hand"]
TUMBLE_DRY = ["any", "low", "medium", "high", "no"]
IRON_TEMP = ["any", "low", "medium", "high", "no"]
BLEACH = ["any", "non_chlorine", "no"]
DRY_CLEAN = ["any", "petroleum", "no"]

# Laundry loads are grouped by these; mixing them is what ruins clothes.
COLOUR_GROUPS = ["whites", "lights", "darks", "colours", "delicates"]

# Reference colours for naming an extracted RGB triple in plain English.
COLOUR_NAMES = [
    ("black", (0, 0, 0)), ("charcoal", (54, 54, 58)), ("grey", (128, 128, 128)),
    ("silver", (192, 192, 192)), ("white", (255, 255, 255)), ("cream", (245, 238, 220)),
    ("beige", (222, 200, 165)), ("tan", (196, 154, 108)), ("brown", (110, 74, 46)),
    ("burgundy", (110, 30, 50)), ("red", (200, 40, 40)), ("orange", (230, 126, 34)),
    ("mustard", (214, 174, 44)), ("yellow", (240, 220, 60)), ("olive", (110, 116, 60)),
    ("green", (60, 150, 80)), ("teal", (40, 130, 130)), ("navy", (26, 40, 78)),
    ("blue", (52, 100, 190)), ("denim", (90, 120, 160)), ("light blue", (150, 190, 225)),
    ("purple", (120, 70, 160)), ("pink", (230, 150, 180)), ("khaki", (160, 150, 110)),
    # Metal tones — jewellery and watches are first-class items here, and gold
    # versus silver is the thing you actually match on.
    ("gold", (212, 175, 55)), ("rose gold", (200, 150, 130)),
]

METAL_TONES = {"gold", "rose gold", "silver"}

# Colour-group inference for laundry batching.
DARK_COLOURS = {"black", "charcoal", "navy", "burgundy", "brown", "olive", "denim"}
LIGHT_COLOURS = {"white", "cream", "beige", "silver", "light blue"}
