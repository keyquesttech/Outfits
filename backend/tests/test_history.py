"""Checks for back-dating a wear.

Everything here runs offline. The parts that talk to Open-Meteo are exercised by
hand; what is worth pinning down in a test is the logic around them — that a day
which has not happened is refused, that a source answering with nulls cannot
wipe a good cached reading, and that moving a wear does not leave the wear
counters or the calibration describing the old day.

    PYTHONPATH=backend .venv/bin/python backend/tests/test_history.py
"""

import os
import sys
import tempfile
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["OUTFITS_DATA"] = tempfile.mkdtemp(prefix="outfits-hist-")

from app import db, recommend                                     # noqa: E402
from app.weather import history                                   # noqa: E402


def fresh():
    conn = db.get_conn()
    conn.executescript(
        "DELETE FROM weather_days; DELETE FROM comfort_feedback; "
        "DELETE FROM wear_log_items; DELETE FROM wear_log; DELETE FROM items;")
    conn.commit()


def day(offset):
    return (date.today() - timedelta(days=offset)).isoformat()


# ------------------------------------------------------- guards

def test_a_day_that_has_not_happened_is_refused():
    fresh()
    result = history.for_date((date.today() + timedelta(days=2)).isoformat())
    assert result["available"] is False
    assert "not happened" in result["reason"]


def test_nonsense_is_not_a_date():
    fresh()
    assert history.for_date("tuesday")["available"] is False
    assert history.for_date("")["available"] is False


# ------------------------------------------------------- caching

def test_a_reading_is_cached_and_read_back():
    fresh()
    history._store([{
        "day": day(3), "temp_c": 11.0, "apparent_c": 9.5, "rain_chance": 40.0,
        "wind_kph": 18.0, "code": 3,
    }], 51.5072, -0.1276)
    hit = history.cached(day(3), 51.5072, -0.1276)
    assert hit["apparent_c"] == 9.5
    assert hit["condition"]["label"] == "Overcast"
    assert hit["available"] is True


def test_nearby_coordinates_are_the_same_place():
    """A GPS reading that wobbles by a few metres must not miss the cache."""
    fresh()
    history._store([{"day": day(3), "temp_c": 11.0, "apparent_c": 9.5,
                     "rain_chance": None, "wind_kph": None, "code": 0}],
                   51.50721, -0.12764)
    assert history.cached(day(3), 51.50718, -0.12759) is not None


def test_an_empty_answer_cannot_wipe_a_good_one():
    """The whole reason the source fallback exists.

    The forecast endpoint returns nulls for days beyond its real coverage. If
    those nulls were stored they would overwrite what the archive had already
    filled in, and the day would go blank on the next read.
    """
    fresh()
    good = {"day": day(80), "temp_c": 17.0, "apparent_c": 16.0,
            "rain_chance": None, "wind_kph": 12.0, "code": 3}
    history._store([good], 51.5072, -0.1276)
    empty = {**good, "temp_c": None, "apparent_c": None, "wind_kph": None, "code": None}
    history._store([empty], 51.5072, -0.1276)
    assert history.cached(day(80), 51.5072, -0.1276)["apparent_c"] == 16.0


def test_a_day_with_no_reading_is_not_cached_as_available():
    fresh()
    history._store([{"day": day(5), "temp_c": None, "apparent_c": None,
                     "rain_chance": None, "wind_kph": None, "code": None}],
                   51.5072, -0.1276)
    assert history.cached(day(5), 51.5072, -0.1276) is None


# ------------------------------------------------------- parsing

def test_a_day_is_summarised_by_its_midpoint():
    parsed = history._parse({
        "time": ["2026-07-01"],
        "temperature_2m_max": [24.0], "temperature_2m_min": [14.0],
        "apparent_temperature_max": [26.0], "apparent_temperature_min": [16.0],
        "wind_speed_10m_max": [20.0], "weather_code": [61],
    })
    assert parsed[0]["temp_c"] == 19.0
    assert parsed[0]["apparent_c"] == 21.0


def test_a_short_or_missing_series_does_not_raise():
    """Open-Meteo omits fields the chosen endpoint does not carry."""
    parsed = history._parse({"time": ["2026-07-01", "2026-07-02"],
                             "temperature_2m_max": [24.0]})
    assert len(parsed) == 2
    assert parsed[1]["temp_c"] is None
    assert parsed[0]["temp_c"] == 24.0        # one end still averages to itself


def test_source_order_flips_with_age():
    recent = date.today() - timedelta(days=2)
    old = date.today() - timedelta(days=300)
    assert (date.today() - recent).days <= history.RECENT_DAYS
    assert (date.today() - old).days > history.RECENT_DAYS


# ------------------------------------------------------- calibration

def test_one_verdict_per_wear_however_often_it_is_re_recorded():
    """Moving a wear re-records its comfort against the new day's weather.

    Before this, each move inserted another row and the same single opinion
    counted two, three, four times towards the personal offset.
    """
    fresh()
    log_id = db.execute(
        "INSERT INTO wear_log(worn_on, apparent_c) VALUES (?, ?)", (day(5), 12.0))
    for apparent in (12.0, 4.0, 20.0):
        recommend.record_comfort(apparent, 15, -1, log_id)
    rows = db.query("SELECT * FROM comfort_feedback WHERE wear_log_id = ?", (log_id,))
    assert len(rows) == 1
    assert rows[0]["apparent_c"] == 20.0      # the latest day, not the first


def test_unrelated_wears_keep_their_own_verdicts():
    fresh()
    first = db.execute("INSERT INTO wear_log(worn_on) VALUES (?)", (day(5),))
    second = db.execute("INSERT INTO wear_log(worn_on) VALUES (?)", (day(6),))
    recommend.record_comfort(10.0, 15, -1, first)
    recommend.record_comfort(10.0, 15, 1, second)
    assert len(db.query("SELECT * FROM comfort_feedback")) == 2


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
