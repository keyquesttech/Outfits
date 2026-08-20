"""Checks for outfits that carry alternatives.

Several items on the top, bottom or footwear layer of a saved outfit are
options — wearing it wears one of each, chosen against the weather. Accessories
stack legitimately and are never treated as alternatives.

    PYTHONPATH=backend .venv/bin/python backend/tests/test_outfit_options.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["OUTFITS_DATA"] = tempfile.mkdtemp(prefix="outfits-opt-")

from app import db, recommend                                     # noqa: E402
from app.serializers import outfit_out                            # noqa: E402

db.get_conn()

COLD = {"apparent_c": 2.0, "rain_chance": 0, "wind_kph": 5}
HOT = {"apparent_c": 26.0, "rain_chance": 0, "wind_kph": 5}


def item(layer, warmth, name="x", **extra):
    return {"id": extra.pop("id", 0), "name": name, "layer": layer,
            "warmth": warmth, "formality": 2, "tags": [], **extra}


def outfit_with_options():
    return [
        item("top", 2, "Tee", id=1),
        item("top", 7, "Heavy knit", id=2),
        item("bottom", 4, "Jeans", id=3),
        item("footwear", 3, "Boots", id=4),
        item("accessory", 1, "Belt", id=5),
        item("accessory", 3, "Beanie", id=6),
    ]


def test_cold_day_picks_the_warm_option():
    chosen = recommend.resolve_outfit(outfit_with_options(), COLD)
    names = {i["name"] for i in chosen}
    assert "Heavy knit" in names and "Tee" not in names


def test_hot_day_picks_the_light_option():
    chosen = recommend.resolve_outfit(outfit_with_options(), HOT)
    names = {i["name"] for i in chosen}
    assert "Tee" in names and "Heavy knit" not in names


def test_exactly_one_per_choice_layer():
    chosen = recommend.resolve_outfit(outfit_with_options(), COLD)
    tops = [i for i in chosen if i["layer"] == "top"]
    assert len(tops) == 1


def test_accessories_all_come_along():
    """A belt and a beanie are worn together, not alternatives."""
    chosen = recommend.resolve_outfit(outfit_with_options(), COLD)
    names = {i["name"] for i in chosen}
    assert {"Belt", "Beanie"} <= names


def test_an_outfit_without_options_passes_through_untouched():
    fixed = [item("top", 3, id=1), item("bottom", 4, id=2), item("footwear", 3, id=3)]
    assert recommend.resolve_outfit(fixed, COLD) == fixed


def test_a_dirty_option_loses_to_a_clean_one():
    items = outfit_with_options()
    for i in items:
        if i["name"] == "Heavy knit":
            i["needs_wash"] = True
    chosen = recommend.resolve_outfit(items, COLD)
    # Even on a cold day, the dirty knit is out — the tee is what is wearable.
    assert "Heavy knit" not in {i["name"] for i in chosen}


def test_all_options_dirty_still_yields_an_outfit():
    items = outfit_with_options()
    for i in items:
        if i["layer"] == "top":
            i["needs_wash"] = True
    chosen = recommend.resolve_outfit(items, COLD)
    assert any(i["layer"] == "top" for i in chosen)


def test_serialised_warmth_averages_options_not_sums_them():
    row = {"id": 1, "name": "Gym", "is_favourite": 0, "is_base": 0}
    out = outfit_out(row, outfit_with_options())
    # top mean (2+7)/2 = 4.5, bottom 4, shoes 3 → 11.5 → 12. A sum would say 16.
    assert out["total_warmth"] == 12
    assert out["option_layers"] == {"top": 2}


# ------------------------------------------------------- bases with options

def _fresh_wardrobe():
    conn = db.get_conn()
    conn.executescript("DELETE FROM item_tags; DELETE FROM tags; DELETE FROM items;")
    conn.commit()


def _add(name, category, warmth=3):
    return db.execute(
        "INSERT INTO items(name, category, warmth, formality) VALUES (?,?,?,2)",
        (name, category, warmth))


MILD = {"apparent_c": 18.0, "rain_chance": 0, "wind_kph": 0}


def test_a_base_with_two_bottoms_pins_exactly_one():
    """The reported bug: a base holding options put both pairs of pants in
    every suggestion. One per layer is what "options" means."""
    _fresh_wardrobe()
    pants_a = _add("Joggers", "bottom", 4)
    pants_b = _add("Track pants", "bottom", 4)
    _add("Tee", "shirt")
    _add("Other tee", "shirt")
    _add("Trainers", "footwear")
    result = recommend.suggest(MILD, count=3, pinned=[pants_a, pants_b], samples=200)
    assert result["suggestions"], "expected suggestions"
    for s in result["suggestions"]:
        bottoms = set(s["item_ids"]) & {pants_a, pants_b}
        assert len(bottoms) == 1, f"suggestion wore {len(bottoms)} bottoms"


def test_both_options_get_explored_across_samples():
    """With enough wardrobe variety, different suggestions can carry different
    base options. (The diversity filter demands suggestions differ by two or
    more items, so a one-top wardrobe could never show the second pair.)"""
    _fresh_wardrobe()
    pants_a = _add("Joggers", "bottom", 4)
    pants_b = _add("Track pants", "bottom", 4)
    for n in ("Tee", "Other tee", "Third tee", "Fourth tee"):
        _add(n, "shirt")
    _add("Trainers", "footwear")
    seen = set()
    result = recommend.suggest(MILD, count=8, pinned=[pants_a, pants_b], samples=300)
    for s in result["suggestions"]:
        seen |= set(s["item_ids"]) & {pants_a, pants_b}
    assert seen == {pants_a, pants_b}, "one option was never offered"


def test_pinned_accessories_still_stack():
    _fresh_wardrobe()
    _add("Tee", "shirt")
    _add("Jeans", "bottom", 4)
    _add("Trainers", "footwear")
    belt = _add("Belt", "belt", 0)
    beanie = _add("Beanie", "headwear", 2)
    result = recommend.suggest(MILD, count=2, pinned=[belt, beanie], samples=150)
    for s in result["suggestions"]:
        assert {belt, beanie} <= set(s["item_ids"])


def test_a_pinned_mid_always_joins_even_on_a_mild_day():
    _fresh_wardrobe()
    _add("Tee", "shirt")
    _add("Jeans", "bottom", 4)
    _add("Trainers", "footwear")
    hoodie = _add("Hoodie", "mid", 5)
    result = recommend.suggest(MILD, count=2, pinned=[hoodie], samples=150)
    for s in result["suggestions"]:
        assert hoodie in set(s["item_ids"])


def test_base_flag_survives_serialisation():
    row = {"id": 1, "name": "Gym", "is_favourite": 0, "is_base": 1}
    assert outfit_out(row, [])["is_base"] is True


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  ok   {name}")
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL {name}: {exc}")
        except Exception as exc:                      # noqa: BLE001
            failed += 1
            print(f"  ERROR {name}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
