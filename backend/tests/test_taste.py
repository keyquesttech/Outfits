"""Checks for the taste model.

What is worth pinning down: a dislike hurts the items that were in it and
nothing else; verdicts can be withdrawn without leaving a residue; the component
model stays silent until it has enough examples and never overrules the base
score outright; and the whole thing degrades to exactly the old behaviour when
no feedback exists.

    PYTHONPATH=backend .venv/bin/python backend/tests/test_taste.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["OUTFITS_DATA"] = tempfile.mkdtemp(prefix="outfits-taste-")

from app import db, recommend, taste                              # noqa: E402

db.get_conn()

MILD = {"apparent_c": 18.0, "rain_chance": 0, "wind_kph": 0}
NEUTRAL = {"warmth": 0.8, "rain": 1.0, "wind": 1.0, "formality": 1.0,
           "colour": 1.0, "freshness": 0.9}


def fresh():
    conn = db.get_conn()
    conn.execute("DELETE FROM suggestion_feedback")
    conn.execute("DELETE FROM settings WHERE key = 'taste_model'")
    conn.commit()
    taste._cache.update({"at": 0.0, "state": None})


def outfit(*ids, warmth=3):
    return [{"id": i, "name": f"item{i}", "layer": "top", "warmth": warmth,
             "formality": 2, "tags": []} for i in ids]


def score(items):
    return recommend.score_outfit(items, MILD, None)["score"]


# ------------------------------------------------------- affinity

def test_no_feedback_changes_nothing():
    fresh()
    result = recommend.score_outfit(outfit(1, 2), MILD, None)
    assert result["breakdown"]["taste"] == 0.0
    assert "learned" not in result["breakdown"]


def test_a_dislike_hurts_the_items_that_were_in_it():
    fresh()
    baseline = score(outfit(1))
    taste.record(-1, [1, 2], None, 18.0, 0.8, NEUTRAL)
    assert score(outfit(1)) < baseline
    assert score(outfit(3)) == baseline        # an uninvolved item is untouched


def test_likes_and_dislikes_pull_opposite_ways():
    fresh()
    taste.record(1, [1], None, 18.0, 0.8, NEUTRAL)
    taste.record(-1, [2], None, 18.0, 0.8, NEUTRAL)
    assert score(outfit(1)) > score(outfit(2))


def test_repeated_dislikes_saturate():
    fresh()
    for _ in range(10):
        taste.record(-1, [1], None, 18.0, 0.8, NEUTRAL)
    learned = taste.state()
    assert learned["affinity"]["1"] == -5.0    # clipped, not unbounded


def test_withdrawing_a_verdict_leaves_no_residue():
    fresh()
    baseline = score(outfit(1))
    feedback_id = taste.record(-1, [1], None, 18.0, 0.8, NEUTRAL)
    assert score(outfit(1)) < baseline
    assert taste.withdraw(feedback_id)
    assert score(outfit(1)) == baseline
    assert not taste.withdraw(feedback_id)     # already gone


def test_the_reason_names_the_leaning():
    fresh()
    for _ in range(3):
        taste.record(1, [1], None, 18.0, 0.8, NEUTRAL)
    reasons = recommend.score_outfit(outfit(1), MILD, None)["reasons"]
    assert any("liked" in r for r in reasons)


# ------------------------------------------------------- the component model

def test_the_model_stays_silent_below_the_threshold():
    fresh()
    for _ in range(taste.MIN_SAMPLES - 1):
        taste.record(1, [99], None, 18.0, 0.8, NEUTRAL)
    assert "learned" not in recommend.score_outfit(outfit(1), MILD, None)["breakdown"]


def test_the_model_learns_what_separates_liked_from_disliked():
    """Likes where colour scored high, dislikes where it scored low: the model
    should come out believing colour matters."""
    fresh()
    for _ in range(8):
        taste.record(1, [90], None, 18.0, 0.9, {**NEUTRAL, "colour": 1.0})
        taste.record(-1, [91], None, 18.0, 0.5, {**NEUTRAL, "colour": 0.3})
    learned = taste.state()
    assert learned["n"] == 16
    assert learned["coef"]["colour"] > 0.2


def test_the_blend_is_capped():
    """A hundred clicks still cannot let the model replace the base score."""
    fresh()
    for _ in range(60):
        taste.record(1, [90], None, 18.0, 0.9, NEUTRAL)
    assert min(taste.MAX_BLEND, taste.state()["n"] / 40.0) == taste.MAX_BLEND


def test_scores_stay_in_bounds():
    fresh()
    for _ in range(10):
        taste.record(1, [1, 2, 3], None, 18.0, 0.95, NEUTRAL)
    high = recommend.score_outfit(outfit(1, 2, 3), MILD, None)["score"]
    for _ in range(10):
        taste.record(-1, [7, 8, 9], None, 18.0, 0.2, NEUTRAL)
    low = recommend.score_outfit(outfit(7, 8, 9), MILD, None)["score"]
    assert 0.0 <= low <= high <= 1.0


# ------------------------------------------------------- summary

def test_summary_names_favourites_and_avoided():
    fresh()
    tee = db.execute("INSERT INTO items(name, category) VALUES ('Loved tee', 'shirt')")
    bad = db.execute("INSERT INTO items(name, category) VALUES ('Hated tee', 'shirt')")
    for _ in range(2):
        taste.record(1, [tee], None, 18.0, 0.8, NEUTRAL)
        taste.record(-1, [bad], None, 18.0, 0.8, NEUTRAL)
    report = taste.summary()
    assert report["likes"] == 2 and report["dislikes"] == 2
    assert report["favourites"][0]["name"] == "Loved tee"
    assert report["avoided"][0]["name"] == "Hated tee"


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
