"""Outfit recommendation.

Scoring is deliberately explainable: every suggestion carries the reasons that
produced it, so a bad suggestion tells you which dial to turn.

The warmth target calibrates to the wearer. Comfort ratings ("too hot", "just
right", "too cold") accumulate in `comfort_feedback` and shift the target, so the
app converges on how *you* experience 12 °C rather than an average body.
"""

import random

from . import categories, colours, db
from .constants import LAYER_ORDER
from .serializers import item_out

WARMTH_LAYERS = ("bottom", "top", "mid", "outer", "footwear")

OCCASION_FORMALITY = {
    "lounge": 1, "sport": 2, "casual": 2, "everyday": 2,
    "work": 3.5, "smart": 4, "date": 4, "party": 4, "formal": 5, "wedding": 5,
}

# What each occasion answers to in an item's tags. Tagging trousers "gym, date"
# commits them: they are preferred for those occasions and left out of the rest.
# An untagged item stays available everywhere and is judged on formality alone.
OCCASION_TAGS = {
    "everyday": {"everyday", "casual"},
    "casual": {"casual", "everyday"},
    "work": {"work", "office"},
    "smart": {"smart"},
    "sport": {"sport", "gym"},
    "date": {"date", "party", "going out"},
    "party": {"date", "party", "going out"},
    "formal": {"formal", "wedding"},
    "wedding": {"formal", "wedding"},
    "lounge": {"lounge"},
}
# "smart" describes how a garment looks, not where it goes — a smart shirt is
# right for work too. It boosts, but never commits an item away from anywhere.
EXCLUSIVE_VOCAB = frozenset(
    t for tags in OCCASION_TAGS.values() for t in tags) - {"smart"}

# Verdict values stored in comfort_feedback.
TOO_COLD, JUST_RIGHT, TOO_HOT = -1, 0, 1

# Above this feels-like temperature, scarves and beanies stay in the drawer.
WARM_ACCESSORY_MAX_C = 15.0


def target_warmth(apparent_c: float) -> float:
    """Desired total insulation for a feels-like temperature.

    Calibrated against real outfits: ~9 at 25 °C (tee, trousers, trainers),
    ~17 at 15 °C (add a jumper), ~30 at 0 °C (add a heavy coat and a scarf).
    """
    return max(7.0, min(36.0, 30.0 - 0.85 * apparent_c))


def personal_offset(limit: int = 40) -> float:
    """Learned correction in warmth units, from recent comfort feedback."""
    rows = db.query(
        "SELECT verdict FROM comfort_feedback ORDER BY id DESC LIMIT ?", (limit,)
    )
    if not rows:
        return 0.0
    verdicts = [int(r["verdict"]) for r in rows]
    mean = sum(verdicts) / len(verdicts)
    # Consistently "too hot" (mean 1.0) pulls the target down by 4 — roughly one layer.
    confidence = min(1.0, len(verdicts) / 8)
    return max(-8.0, min(8.0, -4.0 * mean * confidence))


def record_comfort(apparent_c: float, outfit_warmth: float, verdict: int,
                   wear_log_id: int | None = None) -> float:
    """One verdict per wear.

    Changing a rating, or moving a wear to a different day and re-recording it
    against that day's weather, must replace what was there — inserting a second
    row would count the same opinion twice and drag the offset with it.
    """
    if wear_log_id is not None:
        db.execute("DELETE FROM comfort_feedback WHERE wear_log_id = ?", (wear_log_id,))
    db.execute(
        "INSERT INTO comfort_feedback(wear_log_id, apparent_c, outfit_warmth, verdict) "
        "VALUES (?,?,?,?)",
        (wear_log_id, apparent_c, outfit_warmth, verdict),
    )
    offset = personal_offset()
    db.set_setting("warmth_offset", f"{offset:.2f}")
    return offset


def _rgb(item: dict) -> tuple[int, int, int] | None:
    """The colour to match this item on.

    The colour field wins over the extracted palette: the palette is a guess
    made from pixels, and the field is what the person decided. Whatever is in
    it — "Navy", "dark red", "#1b1b1d" — resolves through the same table the
    rest of the app uses, so a spelling the reference list never happened to
    contain is no longer silently dropped.
    """
    named = colours.rgb_for(item.get("colour_primary"))
    if named:
        return named
    palette = item.get("palette") or []
    rgb = palette[0].get("rgb") if palette else None
    if rgb and len(rgb) >= 3:
        return tuple(int(c) for c in rgb[:3])
    return None


# Below this chroma a garment reads as a neutral: it goes with everything, and
# nothing can clash with it.
CLASHABLE_CHROMA = 12.0


def _hue_family(item: dict):
    """Returns None for anything that cannot clash: neutrals and metals."""
    # Jewellery and watches read as metal, not colour — a gold ring is not a
    # competing hue against a burgundy scarf.
    if item.get("layer") == "jewellery":
        return None
    primary = item.get("colour_primary")
    if colours.is_metal(primary):
        return None
    if colours.canonical(primary) in colours.NEUTRALS:
        return None

    rgb = _rgb(item)
    if not rgb:
        return None
    lightness, chroma, hue = colours.to_lch(rgb)
    if chroma < CLASHABLE_CHROMA or lightness < 12 or lightness > 93:
        return None
    return hue


def colour_harmony(items: list[dict]) -> tuple[float, str]:
    hues = [h for h in (_hue_family(i) for i in items) if h is not None]
    if len(hues) <= 1:
        return 1.0, "neutral palette" if not hues else "one accent colour"

    families: list[float] = []
    for hue in hues:
        if not any(min(abs(hue - f), 360 - abs(hue - f)) < 25 for f in families):
            families.append(hue)

    if len(families) == 1:
        return 1.0, "single colour family"
    if len(families) == 2:
        gap = abs(families[0] - families[1])
        gap = min(gap, 360 - gap)
        if gap < 45:
            return 0.9, "analogous colours"
        if 150 <= gap <= 210:
            return 0.85, "complementary colours"
        return 0.62, "two colours that sit awkwardly"
    return 0.35, f"{len(families)} competing colours"


def outfit_warmth(items: list[dict]) -> int:
    total = sum(int(i.get("warmth") or 0) for i in items if i.get("layer") in WARMTH_LAYERS)
    # Hats and scarves genuinely matter in the cold, but count for less.
    total += sum(int(i.get("warmth") or 0) for i in items if i.get("layer") == "accessory") // 2
    return total


def score_outfit(items: list[dict], weather: dict, occasion: str | None,
                 offset: float = 0.0) -> dict:
    apparent = weather.get("apparent_c")
    rain_chance = weather.get("rain_chance") or 0
    wind = weather.get("wind_kph") or 0

    reasons: list[str] = []
    warmth = outfit_warmth(items)

    if apparent is None:
        warmth_score = 0.6
        reasons.append("no weather data, warmth not scored")
    else:
        target = target_warmth(apparent) + offset
        gap = warmth - target
        warmth_score = max(0.0, 1.0 - abs(gap) / 12.0)
        if abs(gap) <= 3:
            reasons.append(f"warmth suits {apparent:.0f} °C")
        elif gap > 0:
            reasons.append(f"a little warm for {apparent:.0f} °C")
        else:
            reasons.append(f"light for {apparent:.0f} °C")

    rain_score = 1.0
    if rain_chance >= 40:
        if any(i.get("water_proof") for i in items):
            reasons.append(f"waterproof layer for {rain_chance:.0f}% rain")
        else:
            rain_score = 0.45
            reasons.append(f"{rain_chance:.0f}% rain and nothing waterproof")

    wind_score = 1.0
    if wind >= 28:
        if any(i.get("wind_proof") for i in items):
            reasons.append("windproof outer")
        else:
            wind_score = 0.7
            reasons.append(f"windy at {wind:.0f} km/h")

    formality_score = 1.0
    if occasion:
        want = OCCASION_FORMALITY.get(occasion.lower())
        values = [int(i["formality"]) for i in items if i.get("formality")]
        if want and values:
            actual = sum(values) / len(values)
            formality_score = max(0.0, 1.0 - abs(actual - want) / 3.0)
            if formality_score > 0.75:
                reasons.append(f"dressed right for {occasion}")
            else:
                reasons.append(f"formality is off for {occasion}")

    harmony_score, harmony_note = colour_harmony(items)
    reasons.append(harmony_note)

    # Nudge towards things that have not been worn lately.
    worn_counts = [int(i.get("total_wears") or 0) for i in items]
    avg_worn = sum(worn_counts) / len(worn_counts) if worn_counts else 0
    freshness = 1.0 / (1.0 + avg_worn / 25.0)

    total = (
        0.42 * warmth_score
        + 0.16 * rain_score
        + 0.07 * wind_score
        + 0.15 * formality_score
        + 0.14 * harmony_score
        + 0.06 * freshness
    )

    # Explicit taste outranks inference: pieces the wearer filed under this
    # occasion pull the outfit up, over anything the formality average guessed.
    occasion_bonus = 0.0
    if occasion:
        wanted = OCCASION_TAGS.get(occasion.lower(), set())
        tagged = sum(1 for i in items
                     if wanted & {str(t).lower() for t in (i.get("tags") or [])})
        if tagged:
            occasion_bonus = 0.05 * min(tagged, 2)
            total = min(1.0, total + occasion_bonus)
            reasons.append(f"tagged for {occasion}" if tagged == 1
                           else f"{tagged} pieces tagged for {occasion}")

    return {
        "score": round(total, 4),
        "warmth": warmth,
        "target_warmth": round(target_warmth(apparent) + offset, 1) if apparent is not None else None,
        "reasons": reasons,
        "breakdown": {
            "warmth": round(warmth_score, 3),
            "rain": round(rain_score, 3),
            "wind": round(wind_score, 3),
            "formality": round(formality_score, 3),
            "colour": round(harmony_score, 3),
            "freshness": round(freshness, 3),
            "occasion_bonus": round(occasion_bonus, 3),
        },
    }


def tags_by_item() -> dict[int, set[str]]:
    out: dict[int, set[str]] = {}
    for r in db.query(
        "SELECT item_tags.item_id AS item_id, tags.name AS name "
        "FROM item_tags JOIN tags ON tags.id = item_tags.tag_id"
    ):
        out.setdefault(r["item_id"], set()).add(str(r["name"]).lower())
    return out


def _pools(exclude_dirty: bool, seasons: list[str] | None,
           occasion: str | None = None,
           tag_map: dict[int, set[str]] | None = None) -> dict[str, list[dict]]:
    clause = "SELECT * FROM items WHERE is_active = 1"
    params: list = []
    if exclude_dirty:
        clause += " AND status NOT IN ('needs_wash','in_wash')"
    rows = db.query(clause, tuple(params))
    catalogue = categories.by_key()
    tag_map = tag_map or {}
    wanted = OCCASION_TAGS.get((occasion or "").lower(), set())
    pools: dict[str, list[dict]] = {layer: [] for layer in LAYER_ORDER}
    for row in rows:
        item = item_out(row, catalogue)
        item_tags = tag_map.get(item["id"], set())
        item["tags"] = sorted(item_tags)
        if seasons and item["seasons"] and not set(item["seasons"]) & set(seasons):
            continue
        if wanted:
            # An item tagged with occasions belongs to those occasions. Gym
            # joggers do not turn up in a date outfit; an untagged tee still
            # turns up everywhere.
            committed = item_tags & EXCLUSIVE_VOCAB
            if committed and not (committed & wanted):
                continue
        pools.setdefault(item["layer"], []).append(item)
    return pools


def suggest(weather: dict, occasion: str | None = None, count: int = 3,
            exclude_dirty: bool = True, seasons: list[str] | None = None,
            samples: int = 600, pinned: list[int] | None = None) -> dict:
    """Sample candidate outfits, score them, return the best distinct few.

    Sampling beats enumerating: a 200-item wardrobe has millions of combinations,
    and 600 samples on a Pi 4 takes a few milliseconds while still finding the
    good ones because the pools are small per layer.
    """
    tag_map = tags_by_item()
    pools = _pools(exclude_dirty, seasons, occasion, tag_map)
    offset = personal_offset()
    apparent = weather.get("apparent_c")
    target = target_warmth(apparent) + offset if apparent is not None else 18

    pinned_items = []
    if pinned:
        from .serializers import load_items
        pinned_items = load_items(pinned)
        for item in pinned_items:
            item["tags"] = sorted(tag_map.get(item["id"], set()))
    pinned_layers = {i["layer"] for i in pinned_items}

    # A dress or a pair of pyjamas covers top and bottom on its own, so it is a
    # complete layer pair rather than something to wear with trousers.
    one_piece = {k for k, c in categories.by_key().items() if c["one_piece"]}
    one_pieces = [i for i in pools.get("top", []) if i.get("category") in one_piece]
    tops = [i for i in pools.get("top", []) if i.get("category") not in one_piece]
    bottoms = pools.get("bottom", [])
    shoes = pools.get("footwear", [])
    mids = pools.get("mid", [])
    outers = pools.get("outer", [])
    accessories = pools.get("accessory", [])
    jewellery = pools.get("jewellery", [])

    missing = []
    if not tops and not one_pieces:
        missing.append("top")
    if not bottoms and not one_pieces:
        missing.append("bottom")
    if not shoes:
        missing.append("footwear")
    if missing:
        return {
            "suggestions": [],
            "missing_categories": missing,
            "target_warmth": round(target, 1),
            "personal_offset": round(offset, 2),
            "message": "Add at least one " + ", ".join(missing) + " to get suggestions.",
        }

    def pick(pool, layer):
        for item in pinned_items:
            if item["layer"] == layer:
                return item
        return random.choice(pool) if pool else None

    # A scarf or a beanie is insulation, not decoration. No amount of arithmetic
    # makes one right at 23 °C, so gate them on the actual temperature rather
    # than on how far the outfit sits below its warmth target.
    warm_ok = apparent is None or apparent <= WARM_ACCESSORY_MAX_C

    seen: set[tuple] = set()
    scored: list[dict] = []
    for _ in range(samples):
        chosen: list[dict] = []
        if one_pieces and not bottoms:
            use_one_piece = True
        elif one_pieces and "bottom" not in pinned_layers:
            use_one_piece = random.random() < 0.25
        else:
            use_one_piece = False

        if use_one_piece:
            chosen.append(pick(one_pieces, "top") or random.choice(one_pieces))
        else:
            top = pick(tops, "top")
            bottom = pick(bottoms, "bottom")
            if not top or not bottom:
                continue
            chosen += [top, bottom]

        shoe = pick(shoes, "footwear")
        if shoe:
            chosen.append(shoe)

        current = outfit_warmth(chosen)
        if mids and (current < target - 3 or random.random() < 0.3):
            mid = pick(mids, "mid")
            if mid:
                chosen.append(mid)
                current = outfit_warmth(chosen)
        if outers and (current < target - 4 or random.random() < 0.2):
            outer = pick(outers, "outer")
            if outer:
                chosen.append(outer)
        if accessories and random.random() < 0.45:
            pool = [a for a in accessories if int(a.get("warmth") or 0) <= 1 or warm_ok]
            # A belt is pointless with elasticated joggers, and looks wrong with a
            # dress, so it only joins an outfit whose bottom half accepts one.
            belted = next((c for c in chosen if c.get("layer") == "bottom"), None)
            if not belted or not belted.get("takes_belt", True):
                pool = [a for a in pool if a.get("category") != "belt"]
            if pool:
                chosen.append(random.choice(pool))
        if jewellery and random.random() < 0.4:
            chosen.append(random.choice(jewellery))

        for item in pinned_items:  # honour pins that no layer slot covered
            if item["id"] not in {c["id"] for c in chosen}:
                chosen.append(item)

        key = tuple(sorted(c["id"] for c in chosen))
        if key in seen:
            continue
        seen.add(key)
        result = score_outfit(chosen, weather, occasion, offset)
        result["items"] = chosen
        result["item_ids"] = list(key)
        scored.append(result)

    scored.sort(key=lambda s: -s["score"])

    # Keep the top few genuinely different from each other.
    picked: list[dict] = []
    for candidate in scored:
        ids = set(candidate["item_ids"])
        if all(len(ids & set(p["item_ids"])) < max(2, len(ids) - 1) for p in picked):
            picked.append(candidate)
        if len(picked) >= count:
            break

    return {
        "suggestions": picked,
        "considered": len(scored),
        "target_warmth": round(target, 1),
        "personal_offset": round(offset, 2),
        "missing_categories": [],
    }
