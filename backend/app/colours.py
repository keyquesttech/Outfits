"""Colour vocabulary, naming and normalisation.

One place decides what a colour *is*, so the photo extractor, the AI tagger, the
laundry sorter, the outfit matcher and the item form all agree. Before this,
each had its own idea: the extractor named a triple by nearest RGB reference,
laundry matched a lower-cased string against two sets, and the recommender
looked the string back up in the reference list. Anything the user typed that
was not spelled exactly like a reference — "Gray", "Dark Red", "N/A" — fell
through all three silently.

Two jobs live here:

*Naming* turns a pixel colour into a word. It is rule-led rather than pure
nearest-neighbour, because photographed garments cluster in places the textbook
references do not. A black t-shirt photographs at L* 10-20, not 0, so nearest
neighbour called every black garment "charcoal"; white fabric photographs at
L* 84-88, not 100, so every white shirt came back "silver". Lightness bands fix
that directly, and hue only gets a vote once there is enough chroma to trust it.

*Normalisation* turns whatever is in the database into that same vocabulary.
It never destroys input it cannot understand — an unknown word is kept, marked
unknown, and shown to the user as something to fix.
"""

from __future__ import annotations

import math
import re

# ---------------------------------------------------------------- colour maths


def to_lab(rgb) -> tuple[float, float, float]:
    """sRGB to CIE Lab (D65). Pure maths, no numpy.

    Naming needs a perceptually uniform space. Distance in RGB (or redmean)
    misreads mid-tones badly — it calls a grey marl "khaki" and tan leather
    "olive", because those sit close in RGB but nowhere near each other to the eye.
    """
    def linear(c):
        c = max(0.0, min(255.0, float(c))) / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (linear(c) for c in tuple(rgb)[:3])
    x = (r * 0.4124 + g * 0.3576 + b * 0.1805) / 0.95047
    y = (r * 0.2126 + g * 0.7152 + b * 0.0722) / 1.00000
    z = (r * 0.0193 + g * 0.1192 + b * 0.9505) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else (7.787 * t) + (16 / 116)

    fx, fy, fz = f(x), f(y), f(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def to_lch(rgb) -> tuple[float, float, float]:
    """Lab in polar form: lightness, chroma, hue angle in degrees."""
    L, a, b = to_lab(rgb)
    return L, math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360.0


def distance(a, b) -> float:
    """Perceptual distance between two RGB triples (CIE76 in Lab)."""
    la, lb = to_lab(a), to_lab(b)
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(la, lb)))


def hex_of(rgb) -> str:
    r, g, b = (max(0, min(255, int(round(c)))) for c in tuple(rgb)[:3])
    return f"#{r:02x}{g:02x}{b:02x}"


def rgb_of_hex(value: str) -> tuple[int, int, int] | None:
    """Parse #rgb, #rrggbb, #rrggbbaa or the same without the hash."""
    text = str(value or "").strip().lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]+", text or ""):
        return None
    if len(text) == 3:
        text = "".join(c * 2 for c in text)
    if len(text) == 8:      # #rrggbbaa — alpha is not a colour
        text = text[:6]
    if len(text) != 6:
        return None
    return tuple(int(text[i:i + 2], 16) for i in (0, 2, 4))


# ---------------------------------------------------------------- vocabulary

# The swatch shown in the UI for each name, and what the matcher falls back to
# when it has only a word and needs a colour.
SWATCHES: dict[str, str] = {
    "black": "#1b1b1d", "charcoal": "#3a3a3e", "grey": "#808080",
    "silver": "#c3c3c1", "white": "#f6f6f4", "cream": "#f0e7d6",
    "beige": "#ddcfb2", "tan": "#c49a6c", "camel": "#b08d57",
    "brown": "#6e4a2e", "rust": "#9c4a25", "burgundy": "#6e1e32",
    "red": "#c82828", "coral": "#ee6f5b", "salmon": "#f2a184",
    "pink": "#e696b4", "orange": "#e67e22", "mustard": "#d6ae2c",
    "yellow": "#f0dc3c", "olive": "#6e743c", "khaki": "#a0966e",
    "sage": "#9aa88f", "green": "#3c9650", "mint": "#a8d8c0",
    "teal": "#288282", "turquoise": "#40c0c0", "navy": "#1a284e",
    "blue": "#3464be", "denim": "#5a78a0", "light blue": "#96bee1",
    "purple": "#7846a0", "lilac": "#c0a8dc", "plum": "#6a3050",
    "gold": "#d4af37", "rose gold": "#c89682", "bronze": "#9c6b30",
}

COLOUR_LIST: list[str] = list(SWATCHES)

# Neutrals carry no hue worth matching on, and the outfit builder treats them as
# going with anything.
NEUTRALS = {"black", "charcoal", "grey", "silver", "white", "cream"}

# Jewellery and watches are first-class items here, and gold versus silver is
# the thing you actually match on — so metal is not a clashing colour.
METAL_TONES = {"gold", "rose gold", "silver", "bronze"}

# Which laundry pile a colour belongs in. Anything unlisted is "colours".
WHITE_COLOURS = {"white"}
LIGHT_COLOURS = {"cream", "beige", "silver", "light blue", "mint", "lilac", "sage"}
DARK_COLOURS = {"black", "charcoal", "navy", "burgundy", "brown", "olive",
                "denim", "plum", "rust", "bronze"}

# Extra sample points that all mean the same word. These exist because
# photographed fabric does not sit where a colour chart says it should — the
# dark reds below are measured off real burgundy t-shirts, not chosen.
_EXEMPLARS: dict[str, list[str]] = {
    "black": ["#000000", "#141414", "#1b1b1d", "#26221f", "#1b1d23", "#2a2a2c"],
    "charcoal": ["#36363a", "#444448", "#3d3835", "#4a4a4a"],
    "grey": ["#6e6e70", "#8f8f8c", "#5f5956"],
    "silver": ["#cdcdc9", "#b5b5b8", "#d5cfcc"],
    "white": ["#ffffff", "#f2f2f0", "#e9e9e7", "#dad7d6"],
    "cream": ["#f5eedc", "#e8dcc4", "#ccbcb3", "#ede3d8"],
    "beige": ["#c8b89a", "#b3a699", "#cfc1a8"],
    "tan": ["#b08a63", "#cb9a77"],
    "brown": ["#51332d", "#452b20", "#614740", "#7a5b46", "#4a3020"],
    "burgundy": ["#4f3338", "#4d2f31", "#5c2333", "#7b3040"],
    "navy": ["#2a3550", "#26304a", "#1e2a44"],
    "olive": ["#5a6142", "#6a7050", "#4e5436"],
    "plum": ["#513048", "#5e3a56"],
    "salmon": ["#eea278", "#f0ac92"],
    "denim": ["#4f6a90", "#6b86ab"],
    "teal": ["#3e6e70", "#2f6f6f"],
    "green": ["#2f6b3c", "#46804f"],
}

# name -> list of Lab points that name owns.
_POINTS: list[tuple[str, tuple[float, float, float]]] = []
for _name, _hex in SWATCHES.items():
    for _sample in [_hex] + _EXEMPLARS.get(_name, []):
        _POINTS.append((_name, to_lab(rgb_of_hex(_sample))))

_CHROMATIC_POINTS = [(n, lab) for n, lab in _POINTS if n not in NEUTRALS]


# ---------------------------------------------------------------- naming

# Below this chroma a colour has no hue worth believing: camera white balance
# alone moves a neutral grey this far.
NEUTRAL_CHROMA = 3.5
# Between NEUTRAL_CHROMA and here the hue is visible but weak. A washed-out
# army-green tee measures C* 4 and reads "grey" by the numbers, so the neutral
# name wins — but the hue name is offered as the first alternative, because the
# person holding the shirt knows it is olive.
MUTED_CHROMA = 8.0
# Fabric this dark or this light is named by lightness whatever the hue says;
# the chroma there is shadow and highlight, not dye.
ALWAYS_BLACK_L = 11.0
ALWAYS_WHITE_L = 93.0

# Lightness bands for a colour with no usable hue. The upper bounds are set from
# photographed garments rather than from a colour chart: black fabric lands at
# L* 10-20 and white fabric at L* 84-88 under normal room light.
_NEUTRAL_BANDS = [(22.0, "black"), (38.0, "charcoal"), (68.0, "grey"),
                  (84.0, "silver"), (101.0, "white")]

# Warm and light with a little chroma is cream, not silver or white.
_CREAM_MIN_L, _CREAM_MIN_B, _CREAM_HUE = 72.0, 4.5, (40.0, 110.0)


def _neutral_name(L: float, b: float, hue: float, chroma: float) -> str:
    if (L >= _CREAM_MIN_L and b >= _CREAM_MIN_B and chroma >= 3.0
            and _CREAM_HUE[0] <= hue <= _CREAM_HUE[1]):
        return "cream"
    for limit, name in _NEUTRAL_BANDS:
        if L < limit:
            return name
    return "white"


# Neutrals in lightness order, so "what else could this be" means the band
# above and the band below.
_NEUTRAL_LADDER = ["black", "charcoal", "grey", "silver", "white"]


def _neutral_neighbours(name: str) -> list[str]:
    if name == "cream":
        return ["white", "silver", "beige"]
    if name not in _NEUTRAL_LADDER:
        return []
    i = _NEUTRAL_LADDER.index(name)
    near = [_NEUTRAL_LADDER[j] for j in (i - 1, i + 1) if 0 <= j < len(_NEUTRAL_LADDER)]
    if name in ("silver", "white"):
        near.append("cream")
    return near


def _weighted_distance(lab: tuple, ref: tuple) -> float:
    """CIE76 with chroma differences forgiven and hue differences emphasised.

    A faded burgundy tee and a chart burgundy are the same colour to a person
    even though one is half the chroma; a burgundy and a brown at identical
    chroma are not. Plain CIE76 weighs those the other way round, which is how
    every dark red garment ended up called "charcoal".
    """
    L1, a1, b1 = lab
    L2, a2, b2 = ref
    c1, c2 = math.hypot(a1, b1), math.hypot(a2, b2)
    dl = L1 - L2
    dc = c1 - c2
    # Squared hue difference, from the Lab identity dH^2 = da^2 + db^2 - dC^2.
    dh_sq = max(0.0, (a1 - a2) ** 2 + (b1 - b2) ** 2 - dc ** 2)
    return math.sqrt((dl / 1.35) ** 2 + (dc / 2.2) ** 2 + dh_sq * 1.25)


def _ranked(lab: tuple, points) -> list[tuple[str, float]]:
    """Best distance per name, closest first."""
    best: dict[str, float] = {}
    for name, ref in points:
        d = _weighted_distance(lab, ref)
        if d < best.get(name, math.inf):
            best[name] = d
    return sorted(best.items(), key=lambda kv: kv[1])


def classify(rgb, *, allow_metals: bool = False) -> dict:
    """Name a colour, and say what else it could plausibly be.

    The alternatives matter as much as the answer. Some pairs are genuinely
    undecidable from pixels — a white t-shirt and a very light grey marl both
    photograph at L* 84 on white paper — so the useful behaviour is not to
    guess harder but to put the other reading one tap away in the UI.
    """
    lab = to_lab(rgb)
    L, chroma, hue = to_lch(rgb)
    a, b = lab[1], lab[2]

    if L <= ALWAYS_BLACK_L:
        primary, others = "black", ["charcoal"]
    elif L >= ALWAYS_WHITE_L and chroma < 12:
        primary, others = "white", ["cream", "silver"]
    elif chroma < NEUTRAL_CHROMA:
        # No usable hue at all, so the only honest alternatives are the
        # lightness bands either side — never "burgundy" for a flat grey.
        primary = _neutral_name(L, b, hue, chroma)
        others = _neutral_neighbours(primary)
    elif chroma < MUTED_CHROMA:
        # Hue is visible but weak: name it neutral, offer the hue reading first.
        primary = _neutral_name(L, b, hue, chroma)
        hues = [n for n, _ in _ranked(lab, _CHROMATIC_POINTS)][:2]
        neighbours = [n for n, _ in _ranked(lab, _POINTS) if n != primary and n not in hues]
        others = hues + neighbours[:1]
    else:
        ranked = _ranked(lab, _POINTS)
        chosen = [n for n, _ in ranked]
        primary = chosen[0]
        others = chosen[1:3]

    if not allow_metals:
        # Gold and mustard, silver and light grey, are the same pixels. Only a
        # ring or a watch gets named as metal; a jumper does not.
        if primary in METAL_TONES and primary != "silver":
            primary = next((n for n in others if n not in METAL_TONES), "tan")
        others = [n for n in others if n not in METAL_TONES or n == "silver"]

    alternatives = []
    for name in others:
        if name != primary and name not in alternatives:
            alternatives.append(name)
    return {
        "name": primary,
        "alternatives": alternatives[:2],
        "lightness": round(L, 1),
        "chroma": round(chroma, 1),
        "hue": round(hue, 1),
        "neutral": primary in NEUTRALS,
    }


def name_rgb(rgb, *, allow_metals: bool = False) -> str:
    return classify(rgb, allow_metals=allow_metals)["name"]


# ---------------------------------------------------------------- normalising

# Values that mean "I did not fill this in". The AI tagger and hand-typing both
# produce these, and storing them makes every downstream lookup miss.
BLANKS = {"", "-", "--", "n/a", "na", "n.a.", "none", "null", "nil", "unknown",
          "unspecified", "tbd", "?", "??", "no", "not applicable", "various",
          "multi", "multicolour", "multicolor", "assorted"}

# Words that describe a colour without changing which one it is.
_NOISE = {"colour", "color", "coloured", "colored", "ish", "tone", "toned",
          "shade", "marl", "melange", "mélange", "heather", "heathered",
          "washed", "faded", "vintage", "solid", "plain", "matte", "matt",
          "glossy", "metallic", "muted", "bright", "vivid", "warm", "cool",
          "classic", "true", "very", "mid", "medium"}

_DARKEN = {"black": "black", "grey": "charcoal", "white": "silver",
           "silver": "grey", "cream": "beige", "beige": "tan", "tan": "brown",
           "camel": "brown", "brown": "brown", "red": "burgundy",
           "burgundy": "burgundy", "pink": "plum", "coral": "rust",
           "salmon": "coral", "orange": "rust", "rust": "rust",
           "mustard": "mustard", "yellow": "mustard", "olive": "olive",
           "khaki": "olive", "sage": "olive", "green": "green",
           "mint": "sage", "teal": "teal", "turquoise": "teal",
           "navy": "navy", "blue": "navy", "denim": "navy",
           "light blue": "denim", "purple": "plum", "lilac": "purple",
           "plum": "plum", "gold": "bronze", "bronze": "bronze"}

_LIGHTEN = {"black": "charcoal", "charcoal": "grey", "grey": "silver",
            "silver": "white", "white": "white", "cream": "white",
            "beige": "cream", "tan": "beige", "camel": "tan",
            "brown": "tan", "rust": "orange", "burgundy": "red",
            "red": "coral", "coral": "salmon", "salmon": "salmon",
            "pink": "pink", "orange": "salmon", "mustard": "yellow",
            "yellow": "yellow", "olive": "sage", "khaki": "beige",
            "sage": "mint", "green": "mint", "mint": "mint",
            "teal": "turquoise", "turquoise": "turquoise", "navy": "blue",
            "blue": "light blue", "denim": "light blue",
            "light blue": "light blue", "purple": "lilac", "lilac": "lilac",
            "plum": "purple", "gold": "gold", "bronze": "gold"}

_DARK_WORDS = {"dark", "deep", "rich", "night", "midnight", "jet", "ink", "inky"}
_LIGHT_WORDS = {"light", "pale", "soft", "baby", "powder", "ice", "icy", "sky",
                "dusty", "washed-out"}

# Straight renames. Everything on the left ends up as a name in SWATCHES.
_ALIASES = {
    "gray": "grey", "greys": "grey", "grays": "grey", "gunmetal": "charcoal",
    "slate": "charcoal", "graphite": "charcoal", "anthracite": "charcoal",
    "ash": "grey", "stone": "beige", "sand": "beige", "oatmeal": "cream",
    "ecru": "cream", "ivory": "cream", "off white": "cream", "offwhite": "cream",
    "eggshell": "cream", "bone": "cream", "natural": "cream", "chalk": "white",
    "optic white": "white", "snow": "white", "maroon": "burgundy",
    "wine": "burgundy", "oxblood": "burgundy", "claret": "burgundy",
    "bordeaux": "burgundy", "crimson": "red", "scarlet": "red",
    "cherry": "red", "chocolate": "brown", "coffee": "brown", "mocha": "brown",
    "espresso": "brown", "cocoa": "brown", "chestnut": "brown",
    "walnut": "brown", "taupe": "beige", "biscuit": "beige",
    "toffee": "tan", "caramel": "tan", "honey": "tan", "wheat": "beige",
    "terracotta": "rust", "brick": "rust", "copper": "bronze",
    "peach": "salmon", "apricot": "salmon", "blush": "pink", "rose": "pink",
    "fuchsia": "pink", "magenta": "pink", "lavender": "lilac",
    "mauve": "lilac", "violet": "purple", "aubergine": "plum",
    "eggplant": "plum", "indigo": "navy", "midnight blue": "navy",
    "royal": "blue", "royal blue": "blue", "cobalt": "blue",
    "azure": "blue", "sky": "light blue", "sky blue": "light blue",
    "powder blue": "light blue", "baby blue": "light blue",
    "petrol": "teal", "aqua": "turquoise", "cyan": "turquoise",
    "jade": "teal", "emerald": "green", "forest": "green",
    "forest green": "green", "bottle green": "green", "hunter green": "green",
    "kelly green": "green", "army": "olive", "army green": "olive",
    "military": "olive", "moss": "olive", "khakis": "khaki",
    "lime": "green", "chartreuse": "green", "seafoam": "mint",
    "pistachio": "mint", "mustard yellow": "mustard", "ochre": "mustard",
    "amber": "mustard", "canary": "yellow", "lemon": "yellow",
    "tangerine": "orange", "burnt orange": "rust", "coral pink": "coral",
    "salmon pink": "salmon", "sammon": "salmon", "champagne": "gold",
    "brass": "gold", "platinum": "silver", "steel": "silver",
    "pewter": "grey", "nude": "beige", "camo": "olive",
    "camouflage": "olive", "denim blue": "denim", "jean": "denim",
    "jeans": "denim", "indigo blue": "navy", "teal green": "teal",
    "teal blue": "teal", "sea green": "green", "olive green": "olive",
    "bright white": "white", "pure white": "white",
}

_SPLIT = re.compile(r"\s*(?:/|\\|\||,|;|\band\b|\bwith\b|\bplus\b|&|\+)\s*", re.I)


def _tokens(text: str) -> list[str]:
    cleaned = re.sub(r"[^a-z0-9 ]+", " ", str(text or "").lower())
    return [t for t in cleaned.split() if t and t not in _NOISE]


def _resolve_words(words: list[str]) -> str | None:
    """Turn one colour phrase into a canonical name, honouring modifiers."""
    if not words:
        return None
    phrase = " ".join(words)
    if phrase in SWATCHES:
        return phrase
    if phrase in _ALIASES:
        return _ALIASES[phrase]

    darker = sum(1 for w in words if w in _DARK_WORDS)
    lighter = sum(1 for w in words if w in _LIGHT_WORDS)
    rest = [w for w in words if w not in _DARK_WORDS and w not in _LIGHT_WORDS]

    base = None
    for size in (3, 2, 1):                    # longest phrase that resolves wins
        for start in range(len(rest) - size + 1):
            candidate = " ".join(rest[start:start + size])
            if candidate in SWATCHES:
                base = candidate
            elif candidate in _ALIASES:
                base = _ALIASES[candidate]
            if base:
                break
        if base:
            break
    if base is None:
        return None

    for _ in range(darker):
        base = _DARKEN.get(base, base)
    for _ in range(lighter):
        base = _LIGHTEN.get(base, base)
    return base


def split_colours(text: str) -> list[str]:
    """Every colour named in a free-text field, in order, de-duplicated.

    "Blue/Green" on a belt is two colours, not an unknown one — the second is
    worth keeping as the secondary rather than throwing away.
    """
    raw = str(text or "").strip()
    if not raw or raw.lower() in BLANKS:
        return []
    found: list[str] = []
    for part in _SPLIT.split(raw):
        name = canonical(part)
        if name and name not in found:
            found.append(name)
    if not found:
        name = canonical(raw)
        if name:
            found.append(name)
    return found


def canonical(text: str) -> str | None:
    """Free text to a name in SWATCHES, or None if it is not a colour we know.

    Never guesses: an unrecognised word comes back as None so the caller can
    keep what the user typed rather than overwrite it with something wrong.
    """
    raw = str(text or "").strip()
    if not raw or raw.lower() in BLANKS:
        return None

    rgb = rgb_of_hex(raw)
    if rgb is not None and (raw.startswith("#") or len(raw.strip("#")) in (3, 6, 8)):
        if re.fullmatch(r"[0-9a-fA-F#]+", raw) and not raw.isdigit():
            return name_rgb(rgb, allow_metals=True)

    match = re.fullmatch(r"rgba?\(\s*(\d+)\D+(\d+)\D+(\d+).*\)", raw, re.I)
    if match:
        return name_rgb(tuple(int(g) for g in match.groups()), allow_metals=True)

    words = _tokens(raw)
    if not words or " ".join(words) in BLANKS:
        return None
    resolved = _resolve_words(words)
    if resolved:
        return resolved
    # "navy/black" arrives here when the caller did not split it first.
    for part in _SPLIT.split(raw):
        piece = _resolve_words(_tokens(part))
        if piece:
            return piece
    return None


def normalise(text: str) -> str | None:
    """What should be stored for this field. Unknown words are kept verbatim."""
    raw = str(text or "").strip()
    if not raw or raw.lower() in BLANKS:
        return None
    return canonical(raw) or re.sub(r"\s+", " ", raw)


def describe(text: str) -> dict:
    """Everything the UI needs to render one colour value."""
    raw = str(text or "").strip()
    name = canonical(raw)
    if name:
        return {"value": name, "name": name, "known": True, "hex": SWATCHES[name],
                "group": colour_group(name), "neutral": name in NEUTRALS,
                "metal": name in METAL_TONES}
    return {"value": raw, "name": raw, "known": False, "hex": None,
            "group": "colours", "neutral": False, "metal": False}


def rgb_for(text: str) -> tuple[int, int, int] | None:
    """A representative RGB for a stored colour value, however it was written."""
    raw = str(text or "").strip()
    direct = rgb_of_hex(raw)
    if direct is not None and raw.startswith("#"):
        return direct
    name = canonical(raw)
    return rgb_of_hex(SWATCHES[name]) if name else None


def colour_group(colour_name: str | None) -> str:
    """Which laundry pile a colour belongs in."""
    name = canonical(colour_name)
    if not name:
        return "colours"
    if name in WHITE_COLOURS:
        return "whites"
    if name in LIGHT_COLOURS:
        return "lights"
    if name in DARK_COLOURS:
        return "darks"
    return "colours"


# Names that are the same fabric under different light rather than two colours.
# A black t-shirt photographs as black in the folds and charcoal on the shoulders,
# and recording that as "black, charcoal" describes the lighting, not the shirt.
_SHADES = [("black", "charcoal"), ("charcoal", "grey"), ("grey", "silver"),
           ("silver", "white"), ("silver", "cream"), ("cream", "white"),
           ("cream", "beige"), ("beige", "tan"), ("navy", "denim"),
           ("burgundy", "plum"), ("olive", "khaki"), ("teal", "turquoise")]
_SHADE_OF = {frozenset(pair) for pair in _SHADES}


def same_shade(a: str | None, b: str | None) -> bool:
    """Would a person call these one colour seen in two lights?"""
    first, second = canonical(a), canonical(b)
    if not first or not second:
        return False
    return first == second or frozenset((first, second)) in _SHADE_OF


def is_metal(colour_name: str | None) -> bool:
    return canonical(colour_name) in METAL_TONES


def lookup_table() -> dict[str, str]:
    """Every spelling this module accepts, mapped to what it becomes.

    Generated from the same tables `canonical` uses, and handed to the browser
    so the item form can show the swatch for "Dark Red" as it is typed without a
    round trip — and without a second copy of these rules drifting out of step.
    """
    table: dict[str, str] = {name: name for name in SWATCHES}
    table.update(_ALIASES)
    # Only the modifiers people actually type get pre-expanded. The full set
    # still resolves on the server; the table is a convenience for the form, and
    # a rarer phrase simply tidies itself when the item is saved.
    for word in ("dark", "deep"):
        for base, result in _DARKEN.items():
            table.setdefault(f"{word} {base}", result)
    for word in ("light", "pale"):
        for base, result in _LIGHTEN.items():
            table.setdefault(f"{word} {base}", result)
    return table


def palette_options() -> list[dict]:
    """The full vocabulary, for a picker. Ordered light to dark within families."""
    return [
        {"name": name, "hex": SWATCHES[name], "group": colour_group(name),
         "neutral": name in NEUTRALS, "metal": name in METAL_TONES}
        for name in COLOUR_LIST
    ]
