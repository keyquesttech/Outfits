"""Checks for occasion tags steering the outfit builder.

The rule under test: tagging an item with occasion words ("gym, date") commits
it — preferred for those occasions, left out of the rest — while an untagged
item stays available everywhere. And "smart" describes a garment, not a place,
so it boosts without ever excluding.

    PYTHONPATH=backend .venv/bin/python backend/tests/test_occasions.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["OUTFITS_DATA"] = tempfile.mkdtemp(prefix="outfits-occ-")

from app import db, recommend                                     # noqa: E402


def fresh():
    conn = db.get_conn()
    conn.executescript(
        "DELETE FROM item_tags; DELETE FROM tags; DELETE FROM items;")
    conn.commit()


def add_item(name, category, tags=(), **fields):
    cols = {"name": name, "category": category, "warmth": 3, "formality": 2,
            **fields}
    item_id = db.execute(
        f"INSERT INTO items({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
        tuple(cols.values()))
    for tag in tags:
        db.execute("INSERT OR IGNORE INTO tags(name) VALUES (?)", (tag,))
        row = db.query_one("SELECT id FROM tags WHERE name = ?", (tag,))
        db.execute("INSERT INTO item_tags(item_id, tag_id) VALUES (?,?)",
                   (item_id, row["id"]))
    return item_id


def top_pool(occasion):
    return {i["id"] for i in recommend._pools(
        None, occasion, recommend.tags_by_item())["top"]}


MILD = {"apparent_c": 18.0, "rain_chance": 0, "wind_kph": 0}


# ------------------------------------------------------- commitment

def test_a_committed_item_stays_out_of_other_occasions():
    fresh()
    gym = add_item("Gym tee", "top", tags=("gym",))
    plain = add_item("Plain tee", "top")
    assert gym not in top_pool("date") and plain in top_pool("date")
    assert gym in top_pool("sport") and plain in top_pool("sport")


def test_the_users_own_example_pants_tagged_gym_and_date():
    fresh()
    pants = add_item("Joggers", "bottom", tags=("gym", "date"))
    pool = lambda occ: {i["id"] for i in recommend._pools(
        None, occ, recommend.tags_by_item())["bottom"]}
    assert pants in pool("sport")     # gym answers to sport
    assert pants in pool("date")
    assert pants not in pool("work")
    assert pants not in pool("formal")


def test_no_occasion_means_no_exclusion():
    fresh()
    gym = add_item("Gym tee", "top", tags=("gym",))
    assert gym in top_pool(None)


def test_style_tags_never_commit():
    """"smart" and "comfy" say what a garment is like, not where it goes."""
    fresh()
    smart = add_item("Smart shirt", "top", tags=("smart",))
    comfy = add_item("Comfy tee", "top", tags=("comfy",))
    for occasion in ("work", "date", "everyday", "sport"):
        assert smart in top_pool(occasion)
        assert comfy in top_pool(occasion)


def test_the_night_out_family_is_one_family():
    fresh()
    going_out = add_item("Going-out shirt", "top", tags=("going out",))
    assert going_out in top_pool("date")
    assert going_out in top_pool("party")
    assert going_out not in top_pool("work")


# ------------------------------------------------------- boost

def test_tagged_pieces_lift_the_score():
    tagged = [
        {"layer": "top", "warmth": 3, "formality": 2, "tags": ["gym"]},
        {"layer": "bottom", "warmth": 4, "formality": 2, "tags": []},
        {"layer": "footwear", "warmth": 3, "formality": 2, "tags": []},
    ]
    untagged = [dict(i, tags=[]) for i in tagged]
    a = recommend.score_outfit(tagged, MILD, "sport")
    b = recommend.score_outfit(untagged, MILD, "sport")
    assert a["score"] > b["score"]
    assert a["breakdown"]["occasion_bonus"] > 0
    assert any("tagged for sport" in r for r in a["reasons"])


def test_the_boost_cannot_push_past_certainty():
    perfect = [{"layer": "top", "warmth": 9, "formality": 2, "tags": ["gym"]},
               {"layer": "bottom", "warmth": 4, "formality": 2, "tags": ["gym"]},
               {"layer": "footwear", "warmth": 3, "formality": 2, "tags": ["gym"]}]
    result = recommend.score_outfit(perfect, MILD, "sport")
    assert result["score"] <= 1.0


def test_suggestions_never_contain_a_committed_outsider():
    fresh()
    gym_top = add_item("Gym tee", "top", tags=("gym",))
    add_item("Plain tee", "top")
    add_item("Jeans", "bottom", warmth=4)
    add_item("Boots", "footwear")
    result = recommend.suggest(MILD, occasion="date", count=3)
    assert result["suggestions"], "expected suggestions"
    for s in result["suggestions"]:
        assert gym_top not in set(s["item_ids"])


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
