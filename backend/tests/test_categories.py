"""Checks for the category catalogue.

Categories moved out of `constants` and into the database so they can be added
and removed. These cover the two things that made that risky: the seeded set has
to behave exactly like the constants it replaced, and removing a category must
never orphan the garments filed under it.

Runs under pytest, and on its own with plain python:

    PYTHONPATH=backend .venv/bin/python backend/tests/test_categories.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_TMP = tempfile.mkdtemp(prefix="outfits-cat-")
os.environ["OUTFITS_DATA"] = _TMP

from app import categories, db                                   # noqa: E402
from app import constants                                        # noqa: E402
from app.serializers import item_out                             # noqa: E402


def fresh():
    """A database with the built-in categories seeded and nothing else."""
    db.get_conn().executescript(
        "DELETE FROM item_categories; DELETE FROM items; DELETE FROM categories;")
    categories.seed(db.get_conn())
    db.get_conn().commit()


def add_item(name, category, **fields):
    columns = {"name": name, "category": category, **fields}
    marks = ",".join("?" * len(columns))
    return db.execute(
        f"INSERT INTO items({','.join(columns)}) VALUES ({marks})",
        tuple(columns.values()))


# ------------------------------------------------------- the seeded set

def test_seed_matches_the_constants_it_replaced():
    fresh()
    seeded = categories.by_key()
    assert set(seeded) == set(constants.CATEGORY_LAYERS)
    for key, layer in constants.CATEGORY_LAYERS.items():
        assert seeded[key]["layer"] == layer
        assert seeded[key]["warmth"] == constants.DEFAULT_WARMTH[key]
        assert seeded[key]["formality"] == constants.DEFAULT_FORMALITY[key]
        assert seeded[key]["fit_options"] == constants.FIT_OPTIONS.get(key, [])
        assert seeded[key]["one_piece"] == (key in constants.ONE_PIECE_CATEGORIES)


def test_seed_runs_once():
    fresh()
    assert categories.seed(db.get_conn()) == 0


# ------------------------------------------------------- adding

def test_a_new_category_takes_its_defaults_from_the_layer():
    fresh()
    made = categories.create("gym_kit", "Gym Kit", "outer")
    assert made["layer"] == "outer"
    assert made["warmth"] == 8
    assert made["fit_options"] == ["fitted", "regular", "loose", "oversized"]
    assert made["is_builtin"] is False


def test_explicit_values_beat_the_layer_defaults():
    fresh()
    made = categories.create("swim", "Swim", "base", warmth=0, formality=1)
    assert (made["warmth"], made["formality"]) == (0, 1)


def test_names_that_differ_only_in_case_are_one_category():
    assert categories.slugify("Gym Kit") == categories.slugify("gym  kit")
    assert categories.slugify("Base—Layer!") == "base_layer"


def test_a_new_category_reaches_the_items_that_use_it():
    fresh()
    categories.create("gym_kit", "Gym Kit", "mid")
    item_id = add_item("Hoodie", "gym_kit")
    row = db.query_one("SELECT * FROM items WHERE id = ?", (item_id,))
    item = item_out(row)
    assert item["layer"] == "mid"
    assert item["category_label"] == "Gym Kit"
    assert item["category_known"] is True


# ------------------------------------------------------- counting

def test_counts_include_the_extra_categories_an_item_also_counts_as():
    fresh()
    item_id = add_item("Joggers", "bottom")
    db.execute("INSERT INTO item_categories(item_id, category) VALUES (?, 'pyjamas')",
               (item_id,))
    counted = categories.counts()
    assert counted["bottom"] == 1
    assert counted["pyjamas"] == 1          # the filter finds it under both
    assert "shirt" not in counted           # empty categories are absent


def test_inactive_items_do_not_keep_a_category_on_screen():
    fresh()
    add_item("Old coat", "outerwear", is_active=0)
    assert "outerwear" not in categories.counts()


# ------------------------------------------------------- removing

def test_removing_an_empty_category_just_removes_it():
    fresh()
    assert categories.delete("glasses")["deleted"] is True
    assert "glasses" not in categories.by_key()


def test_removing_an_occupied_category_is_refused():
    fresh()
    add_item("Belt", "belt")
    result = categories.delete("belt")
    assert result["deleted"] is False and result["primary"] == 1
    assert "belt" in categories.by_key()    # nothing was removed


def test_moving_items_out_keeps_them_whole():
    fresh()
    item_id = add_item("Belt", "belt")
    categories.delete("belt", move_to="bag")
    row = db.query_one("SELECT * FROM items WHERE id = ?", (item_id,))
    item = item_out(row)
    assert item["category"] == "bag"
    assert item["layer"] == "accessory"     # still has a slot in an outfit
    assert item["category_known"] is True


def test_moving_an_extra_onto_the_items_own_primary_does_not_collide():
    """The case that would otherwise hit a duplicate primary key.

    An item filed primarily as a shirt, and additionally as a sock, when socks
    are merged into shirts: the extra becomes a duplicate of the primary.
    """
    fresh()
    item_id = add_item("Tee", "shirt")
    db.execute("INSERT INTO item_categories(item_id, category) VALUES (?, 'sock')",
               (item_id,))
    assert categories.delete("sock", move_to="shirt")["deleted"] is True
    extras = db.query("SELECT category FROM item_categories WHERE item_id = ?", (item_id,))
    assert extras == []


def test_two_items_merging_into_one_extra_do_not_collide():
    fresh()
    first, second = add_item("A", "top"), add_item("B", "top")
    for item_id in (first, second):
        db.execute("INSERT INTO item_categories(item_id, category) VALUES (?, 'sock')",
                   (item_id,))
    db.execute("INSERT INTO item_categories(item_id, category) VALUES (?, 'shirt')",
               (first,))
    assert categories.delete("sock", move_to="shirt")["deleted"] is True
    rows = db.query("SELECT item_id, category FROM item_categories ORDER BY item_id")
    assert rows == [{"item_id": first, "category": "shirt"},
                    {"item_id": second, "category": "shirt"}]


def test_an_item_left_in_a_deleted_category_says_so():
    """Legacy rows can name a category the table no longer has."""
    fresh()
    item_id = add_item("Orphan", "something_removed")
    item = item_out(db.query_one("SELECT * FROM items WHERE id = ?", (item_id,)))
    assert item["category_known"] is False
    assert item["layer"] == "accessory"     # a harmless slot, not a crash
    assert item["category_label"] == "Something Removed"


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
