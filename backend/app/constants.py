"""Domain vocabulary: categories, layers, wash defaults, colour naming."""

# Category -> layer slot used by the outfit builder.
CATEGORY_LAYERS = {
    "underwear": "base",
    "sock": "base",
    "top": "top",
    "shirt": "top",
    "bottom": "bottom",
    "dress": "top",
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
    "underwear": 1, "sock": 2, "shirt": 3, "top": 3, "dress": 3,
    "bottom": 4, "mid": 6, "knitwear": 6, "outerwear": 8, "footwear": 3,
    "headwear": 3, "scarf": 4, "glove": 3, "belt": 0, "bag": 0,
    "glasses": 0, "watch": 0, "jewellery": 0,
}

STATUSES = ["clean", "worn", "needs_wash", "airing", "in_wash"]

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
