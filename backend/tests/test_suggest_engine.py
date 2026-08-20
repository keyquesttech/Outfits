"""Checks for exhaustive scoring and pair affinity.

Exhaustive mode replaces dice with enumeration when the space is small enough,
so the things worth pinning down are exactness: the candidate count matches the
arithmetic, the best combination is found deterministically, and the rules the
sampler enforced by construction (belts, pins-as-options) hold as hard filters.

Pair affinity feeds the wear log back into scoring: worn together twice or more
is a habit, once is an accident.

    PYTHONPATH=backend .venv/bin/python backend/tests/test_suggest_engine.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["OUTFITS_DATA"] = tempfile.mkdtemp(prefix="outfits-engine-")

from app import db, recommend                                     # noqa: E402

db.get_conn()

MILD = {"apparent_c": 18.0, "rain_chance": 0, "wind_kph": 0}
COLD = {"apparent_c": 2.0, "rain_chance": 0, "wind_kph": 0}


def fresh():
    conn = db.get_conn()
    conn.executescript(
        "DELETE FROM suggestion_feedback; DELETE FROM wear_log_items; "
        "DELETE FROM wear_log; DELETE FROM item_tags; DELETE FROM tags; "
        "DELETE FROM items;")
    conn.commit()
    recommend.invalidate_pairs()


def add(name, category, warmth=3, takes_belt=1):
    return db.execute(
        "INSERT INTO items(name, category, warmth, formality, takes_belt) "
        "VALUES (?,?,?,2,?)", (name, category, warmth, takes_belt))


def wear_together(ids, day):
    log_id = db.execute("INSERT INTO wear_log(worn_on) VALUES (?)", (day,))
    db.executemany("INSERT INTO wear_log_items(wear_log_id, item_id) VALUES (?,?)",
                   [(log_id, i) for i in ids])
    recommend.invalidate_pairs()


# ------------------------------------------------------- exhaustive mode

def test_small_spaces_are_enumerated_exactly():
    fresh()
    for n in ("T1", "T2"):
        add(n, "shirt")
    add("Jeans", "bottom", 4)
    add("Boots", "footwear")
    result = recommend.suggest(MILD, count=8)
    assert result["method"] == "exhaustive"
    # 2 tops × 1 bottom × 1 shoe, no optional layers: exactly 2 candidates.
    assert result["considered"] == 2


def test_optional_layers_multiply_the_space():
    fresh()
    add("Tee", "shirt")
    add("Jeans", "bottom", 4)
    add("Boots", "footwear")
    add("Hoodie", "mid", 5)
    add("Beanie", "headwear", 1)      # warmth 1 passes the warm-accessory gate
    result = recommend.suggest(MILD, count=8)
    # 1 core × 1 shoe × (mid or not) × (beanie or not) = 4.
    assert result["method"] == "exhaustive"
    assert result["considered"] == 4


def test_belt_combinations_with_beltless_bottoms_are_not_candidates():
    fresh()
    add("Tee", "shirt")
    add("Joggers", "bottom", 4, takes_belt=0)
    add("Boots", "footwear")
    add("Belt", "belt", 0)
    result = recommend.suggest(MILD, count=8)
    # The belt variant is filtered out, leaving only the beltless candidate.
    assert result["considered"] == 1
    for s in result["suggestions"]:
        assert all(i["category"] != "belt" for i in s["items"])


def test_the_best_combination_is_found_deterministically():
    fresh()
    add("Light tee", "shirt", 2)
    heavy = add("Heavy knit", "shirt", 7)
    add("Jeans", "bottom", 4)
    add("Boots", "footwear")
    add("Coat", "outer", 8)
    for _ in range(3):                 # no dice: same answer every time
        result = recommend.suggest(COLD, count=1)
        assert result["method"] == "exhaustive"
        assert heavy in result["suggestions"][0]["item_ids"]


def test_a_big_wardrobe_still_samples():
    fresh()
    for i in range(20):
        add(f"Top{i}", "shirt")
    for i in range(20):
        add(f"Bottom{i}", "bottom", 4)
    for i in range(13):
        add(f"Shoe{i}", "footwear")
    result = recommend.suggest(MILD, count=3, samples=200)
    assert result["method"] == "sampled"     # 20×20×13 = 5200 > 5000


def test_pinned_options_hold_in_exhaustive_mode():
    fresh()
    add("Tee", "shirt")
    a = add("Joggers", "bottom", 4)
    b = add("Track pants", "bottom", 4)
    add("Boots", "footwear")
    result = recommend.suggest(MILD, count=8, pinned=[a, b])
    assert result["method"] == "exhaustive"
    assert result["considered"] == 2         # one candidate per bottom option
    for s in result["suggestions"]:
        assert len(set(s["item_ids"]) & {a, b}) == 1


def test_a_pinned_mid_is_in_every_candidate():
    fresh()
    add("Tee", "shirt")
    add("Jeans", "bottom", 4)
    add("Boots", "footwear")
    hoodie = add("Hoodie", "mid", 5)
    result = recommend.suggest(MILD, count=8, pinned=[hoodie])
    assert all(hoodie in s["item_ids"] for s in result["suggestions"])
    assert result["considered"] == 1         # the mid slot is fixed, not optional


# ------------------------------------------------------- pair affinity

def test_a_repeated_pairing_lifts_the_outfit():
    fresh()
    tee = add("Tee", "shirt")
    jeans = add("Jeans", "bottom", 4)
    other = add("Other tee", "shirt")
    add("Boots", "footwear")
    for day in ("2026-08-01", "2026-08-05", "2026-08-10"):
        wear_together([tee, jeans], day)

    result = recommend.suggest(MILD, count=1)
    best = result["suggestions"][0]
    assert tee in best["item_ids"] and jeans in best["item_ids"]
    assert best["breakdown"]["pairs"] > 0
    assert any("pairing" in r for r in best["reasons"])

    # Same warmth, same everything, no history: scores strictly lower.
    def outfit(top_id):
        rows = db.query("SELECT * FROM items WHERE id IN (?, ?, ?)",
                        (top_id, jeans, best["item_ids"][-1]))
        from app.serializers import item_out
        return [dict(item_out(r), tags=[]) for r in rows]
    habitual = recommend.score_outfit(outfit(tee), MILD, None)["score"]
    novel = recommend.score_outfit(outfit(other), MILD, None)["score"]
    assert habitual > novel


def test_once_together_is_an_accident_not_a_habit():
    fresh()
    tee = add("Tee", "shirt")
    jeans = add("Jeans", "bottom", 4)
    add("Boots", "footwear")
    wear_together([tee, jeans], "2026-08-01")
    result = recommend.suggest(MILD, count=1)
    assert result["suggestions"][0]["breakdown"]["pairs"] == 0


def test_the_bonus_saturates():
    fresh()
    tee = add("Tee", "shirt")
    jeans = add("Jeans", "bottom", 4)
    add("Boots", "footwear")
    for i in range(30):
        wear_together([tee, jeans], f"2026-06-{(i % 28) + 1:02d}")
    result = recommend.suggest(MILD, count=1)
    assert result["suggestions"][0]["breakdown"]["pairs"] <= recommend.PAIR_WEIGHT


def test_the_cache_follows_the_log():
    fresh()
    tee = add("Tee", "shirt")
    jeans = add("Jeans", "bottom", 4)
    add("Boots", "footwear")
    assert recommend.pair_counts() == {}
    wear_together([tee, jeans], "2026-08-01")   # wear_together invalidates
    wear_together([tee, jeans], "2026-08-02")
    key = tuple(sorted((tee, jeans)))
    assert recommend.pair_counts()[key] == 2


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
