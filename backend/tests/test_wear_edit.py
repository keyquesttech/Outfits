"""Checks for editing a logged wear's items.

Replacing the items is a diff: removed pieces get their wear back, added ones
are counted, unchanged ones keep their history untouched.

    PYTHONPATH=backend .venv/bin/python backend/tests/test_wear_edit.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["OUTFITS_DATA"] = tempfile.mkdtemp(prefix="outfits-wedit-")

from fastapi import HTTPException                                 # noqa: E402

from app import db                                                # noqa: E402
from app.models import WearIn, WearPatch                          # noqa: E402
from app.routers.wear import log_wear, update_wear                # noqa: E402

db.get_conn()


def fresh():
    conn = db.get_conn()
    conn.executescript(
        "DELETE FROM comfort_feedback; DELETE FROM wear_log_items; "
        "DELETE FROM wear_log; DELETE FROM items;")
    conn.commit()


def add(name, category="shirt", warmth=3):
    return db.execute(
        "INSERT INTO items(name, category, warmth, formality) VALUES (?,?,?,2)",
        (name, category, warmth))


def counters(item_id):
    row = db.query_one(
        "SELECT total_wears, last_worn FROM items WHERE id = ?", (item_id,))
    return (row["total_wears"], row["last_worn"])


def test_swapping_an_item_moves_the_counters_with_it():
    fresh()
    tee, knit, jeans = add("Tee"), add("Knit"), add("Jeans", "bottom")
    wear = log_wear(WearIn(item_ids=[tee, jeans], worn_on="2026-08-10",
                           use_weather=False))["wear"]
    assert counters(tee) == (1, "2026-08-10")
    assert counters(knit) == (0, None)

    update_wear(wear["id"], WearPatch(item_ids=[knit, jeans]))
    assert counters(tee) == (0, None), "removed item kept its wear"
    assert counters(knit) == (1, "2026-08-10"), "added item not counted"
    assert counters(jeans) == (1, "2026-08-10"), "unchanged item was touched"


def test_unchanged_items_keep_their_history():
    fresh()
    tee, jeans = add("Tee"), add("Jeans", "bottom")
    wear = log_wear(WearIn(item_ids=[tee, jeans], worn_on="2026-08-10",
                           use_weather=False))["wear"]
    before = counters(jeans)
    update_wear(wear["id"], WearPatch(item_ids=[tee, jeans], notes="same items"))
    assert counters(jeans) == before


def test_an_empty_item_list_is_refused():
    fresh()
    tee = add("Tee")
    wear = log_wear(WearIn(item_ids=[tee], worn_on="2026-08-10",
                           use_weather=False))["wear"]
    try:
        update_wear(wear["id"], WearPatch(item_ids=[]))
        raise AssertionError("expected 400")
    except HTTPException as exc:
        assert exc.status_code == 400


def test_an_unknown_item_is_refused_whole():
    fresh()
    tee = add("Tee")
    wear = log_wear(WearIn(item_ids=[tee], worn_on="2026-08-10",
                           use_weather=False))["wear"]
    try:
        update_wear(wear["id"], WearPatch(item_ids=[tee, 9999]))
        raise AssertionError("expected 400")
    except HTTPException as exc:
        assert exc.status_code == 400
    assert counters(tee) == (1, "2026-08-10")   # nothing half-applied


def test_comfort_is_rerecorded_against_the_new_outfit():
    """The verdict was about how warm the outfit was; the outfit just changed."""
    fresh()
    tee, knit = add("Tee", warmth=2), add("Knit", warmth=8)
    wear = log_wear(WearIn(item_ids=[tee], worn_on="2026-08-10",
                           apparent_c=10.0, use_weather=False))["wear"]
    update_wear(wear["id"], WearPatch(comfort_rating=-1))
    first = db.query_one("SELECT outfit_warmth FROM comfort_feedback WHERE wear_log_id = ?",
                         (wear["id"],))["outfit_warmth"]
    update_wear(wear["id"], WearPatch(item_ids=[knit]))
    rows = db.query("SELECT outfit_warmth FROM comfort_feedback WHERE wear_log_id = ?",
                    (wear["id"],))
    assert len(rows) == 1
    assert rows[0]["outfit_warmth"] > first


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
