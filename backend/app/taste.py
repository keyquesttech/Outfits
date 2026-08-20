"""Taste: what liking and disliking suggestions teaches the recommender.

Every thumb on a suggestion is a labelled example, and two things are learned
from them, both cheap enough to retrain on every tap and both explainable:

*Item affinity.* Each verdict counts for or against every item in the judged
outfit. Dislike three outfits containing the salmon tee and the tee itself is
carrying the signal — future outfits containing it score lower, whatever else
they got right. This is the part weight-learning cannot do, because the score
components never mention which garment is which.

*Component weighting.* The hand-set weights (warmth 0.42, colour 0.14, …) are a
guess about what matters to an average person. A small logistic model over the
same components learns what actually separates liked from disliked for *this*
person, and its opinion is blended in gradually — nothing moves until there are
MIN_SAMPLES verdicts, and the blend never exceeds MAX_BLEND, so the hand-set
score remains the backbone rather than being replaced by a model trained on
thirty clicks.
"""

import json
import math
import time

from . import db

# The score components the model learns over. Taste's own outputs are
# deliberately absent: training a model on its own adjustments feeds back.
FEATURES = ("warmth", "rain", "wind", "formality", "colour", "freshness")

# Below this many verdicts the component model stays silent. Item affinity
# works from the first tap — one dislike is already information about an item.
MIN_SAMPLES = 6
# The most the learned model can pull the score away from the hand-set one.
MAX_BLEND = 0.4
# How hard a single item's affinity can push an outfit, at saturation.
AFFINITY_WEIGHT = 0.08

_cache: dict = {"at": 0.0, "state": None}
CACHE_SECONDS = 5.0


def record(verdict: int, item_ids: list[int], occasion: str | None,
           apparent_c: float | None, score: float | None, breakdown: dict) -> int:
    feedback_id = db.execute(
        "INSERT INTO suggestion_feedback(verdict, item_ids, occasion, apparent_c, "
        "score, breakdown) VALUES (?,?,?,?,?,?)",
        (verdict, json.dumps(sorted(item_ids)), occasion, apparent_c, score,
         json.dumps({k: breakdown.get(k) for k in FEATURES})),
    )
    _relearn()
    return feedback_id


def withdraw(feedback_id: int) -> bool:
    row = db.query_one("SELECT id FROM suggestion_feedback WHERE id = ?", (feedback_id,))
    if not row:
        return False
    db.execute("DELETE FROM suggestion_feedback WHERE id = ?", (feedback_id,))
    _relearn()
    return True


def counts() -> dict:
    row = db.query_one(
        "SELECT SUM(verdict = 1) AS likes, SUM(verdict = -1) AS dislikes "
        "FROM suggestion_feedback") or {}
    return {"likes": row.get("likes") or 0, "dislikes": row.get("dislikes") or 0}


def state() -> dict:
    """The learned model, cached briefly — scoring calls this 600 times a request."""
    now = time.time()
    if _cache["state"] is not None and now - _cache["at"] < CACHE_SECONDS:
        return _cache["state"]
    stored = db.get_setting("taste_model", "")
    if stored:
        try:
            learned = json.loads(stored)
        except ValueError:
            learned = _learn()
    else:
        learned = _learn()
    _cache.update({"at": now, "state": learned})
    return learned


def _relearn() -> None:
    learned = _learn()
    db.set_setting("taste_model", json.dumps(learned))
    _cache.update({"at": time.time(), "state": learned})


def _learn() -> dict:
    rows = db.query("SELECT verdict, item_ids, breakdown FROM suggestion_feedback")

    affinity: dict[str, float] = {}
    samples = []
    for row in rows:
        verdict = int(row["verdict"])
        for item_id in db.loads(row["item_ids"], []):
            key = str(item_id)
            # Clipped so one item cannot accumulate unbounded hatred: five
            # verdicts saturate it, and a change of heart can still dig it out.
            affinity[key] = max(-5.0, min(5.0, affinity.get(key, 0.0) + verdict))
        features = db.loads(row["breakdown"], {})
        samples.append(({f: float(features.get(f, 0.5) or 0.5) for f in FEATURES},
                        1.0 if verdict > 0 else 0.0))

    return {
        "n": len(samples),
        "affinity": affinity,
        **_train(samples),
    }


def _train(samples: list) -> dict:
    """Logistic regression, ridge-regularised towards zero.

    Zero coefficients mean "no opinion": the blend then predicts 0.5 everywhere
    and pulls nothing. Regularisation keeps thirty clicks from producing a model
    more confident than thirty clicks deserve.
    """
    if len(samples) < MIN_SAMPLES:
        return {"bias": 0.0, "coef": {f: 0.0 for f in FEATURES}}

    bias = 0.0
    coef = {f: 0.0 for f in FEATURES}
    rate, ridge = 0.5, 0.05
    n = len(samples)
    for _ in range(300):
        grad_b = 0.0
        grad = {f: 0.0 for f in FEATURES}
        for features, label in samples:
            z = bias + sum(coef[f] * features[f] for f in FEATURES)
            p = 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))
            err = p - label
            grad_b += err
            for f in FEATURES:
                grad[f] += err * features[f]
        bias -= rate * grad_b / n
        for f in FEATURES:
            coef[f] -= rate * (grad[f] / n + ridge * coef[f])
    return {"bias": round(bias, 4), "coef": {f: round(v, 4) for f, v in coef.items()}}


def adjust(total: float, items: list[dict], breakdown: dict) -> tuple[float, list[str]]:
    """Fold the learned taste into a scored outfit. Returns (score, reasons)."""
    learned = state()
    reasons: list[str] = []

    pull = sum(learned["affinity"].get(str(i.get("id")), 0.0) for i in items)
    leaning = math.tanh(pull / 4.0)
    breakdown["taste"] = round(leaning, 3)
    if leaning:
        total = max(0.0, min(1.0, total + AFFINITY_WEIGHT * leaning))
    if leaning >= 0.25:
        reasons.append("close to outfits you liked")
    elif leaning <= -0.25:
        reasons.append("similar to ones you disliked")

    if learned["n"] >= MIN_SAMPLES and any(learned["coef"].values()):
        z = learned["bias"] + sum(
            learned["coef"][f] * float(breakdown.get(f, 0.5) or 0.5) for f in FEATURES)
        predicted = 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))
        blend = min(MAX_BLEND, learned["n"] / 40.0)
        total = (1.0 - blend) * total + blend * predicted
        breakdown["learned"] = round(predicted, 3)

    return total, reasons


def summary() -> dict:
    """What the model currently believes, for the Insights page."""
    learned = state()
    tallies = counts()
    ranked = sorted(((float(v), int(k)) for k, v in learned["affinity"].items()
                     if abs(float(v)) >= 1), reverse=True)
    ids = [item_id for _, item_id in ranked]
    names = {}
    if ids:
        marks = ",".join("?" * len(ids))
        names = {r["id"]: r["name"] for r in db.query(
            f"SELECT id, name FROM items WHERE id IN ({marks})", tuple(ids))}
    favourites = [{"id": i, "name": names.get(i), "pull": v}
                  for v, i in ranked if v > 0 and names.get(i)][:3]
    avoided = [{"id": i, "name": names.get(i), "pull": v}
               for v, i in reversed(ranked) if v < 0 and names.get(i)][:3]
    return {
        **tallies,
        "total": learned["n"],
        "learning": learned["n"] >= MIN_SAMPLES,
        "needed": max(0, MIN_SAMPLES - learned["n"]),
        "favourites": favourites,
        "avoided": avoided,
    }
