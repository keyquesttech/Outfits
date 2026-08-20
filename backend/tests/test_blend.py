"""Checks for the multi-model blend.

The network paths are exercised by hand; what is worth pinning down is the
combining arithmetic — median for temperatures so one model having a bad day
cannot drag the answer, mean for rain probabilities so they stay honest, and a
Met Office member folding in without being able to break anything by failing.

    PYTHONPATH=backend .venv/bin/python backend/tests/test_blend.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.weather import blend                                     # noqa: E402


def daily_fixture():
    """Three models, two days, with the gaps the real feeds produce."""
    return {
        "time": ["2026-08-20", "2026-08-21"],
        # UKMO never reports rain probability — the real feed sends nulls.
        "temperature_2m_max_ukmo_seamless": [21.4, 22.0],
        "temperature_2m_max_ecmwf_ifs025": [21.9, 22.4],
        "temperature_2m_max_icon_seamless": [23.0, 22.8],
        "temperature_2m_max_gfs_seamless": [22.2, None],
        "precipitation_probability_max_ukmo_seamless": [None, None],
        "precipitation_probability_max_ecmwf_ifs025": [97, 20],
        "precipitation_probability_max_icon_seamless": [50, 40],
        "precipitation_probability_max_gfs_seamless": [58, None],
        "weather_code_ukmo_seamless": [61, 3],
        "weather_code_ecmwf_ifs025": [61, 3],
        "weather_code_icon_seamless": [3, 61],
        "weather_code_gfs_seamless": [61, 2],
        "weather_code_best_match": [61, 3],
    }


# ------------------------------------------------------- arithmetic

def test_median_shrugs_off_one_outlier():
    # An even pack averages its middle two; compare rounded, floats being floats.
    assert round(blend.median([21.4, 21.9, 23.0, 22.2]), 2) == 22.05
    assert blend.median([10.0, 10.2, 30.0]) == 10.2      # the outlier loses
    assert blend.median([None, None, 5.0]) == 5.0
    assert blend.median([None, None]) is None


def test_rain_is_averaged_not_medianed():
    combined = blend.combine_daily(daily_fixture())
    # mean(97, 50, 58) = 68.3 → 68; a median would have said 58.
    assert combined["precipitation_probability_max"][0] == 68


def test_temperature_is_the_median_of_the_pack():
    combined = blend.combine_daily(daily_fixture())
    assert combined["temperature_2m_max"][0] == 22.0   # median 22.05, stored to 1 dp
    # Day two: GFS is silent, median of the three that answered.
    assert combined["temperature_2m_max"][1] == 22.4


def test_condition_is_the_majority_vote():
    combined = blend.combine_daily(daily_fixture())
    assert combined["weather_code"][0] == 61              # rain 3-1
    # Day two: 3, 61, 2 — no majority, best_match settles it.
    assert combined["weather_code"][1] == 3


def test_a_null_model_cannot_blank_a_day():
    combined = blend.combine_daily(daily_fixture())
    assert None not in combined["precipitation_probability_max"][:1]


# ------------------------------------------------------- the fifth member

def met_member():
    return {"2026-08-20": {"max_c": 20.0, "rain_chance": 90,
                           "condition": {"code": 61, "group": "rain"}}}


def test_the_datahub_feed_joins_the_vote():
    with_met = blend.combine_daily(daily_fixture(), met_member())
    without = blend.combine_daily(daily_fixture())
    # Rain: mean(97, 50, 58, 90) = 73.75 → 74.
    assert with_met["precipitation_probability_max"][0] == 74
    assert without["precipitation_probability_max"][0] == 68
    # Temperature: an even pack now, median moves down towards the new member.
    assert with_met["temperature_2m_max"][0] < without["temperature_2m_max"][0]


def test_days_the_datahub_does_not_cover_are_untouched():
    with_met = blend.combine_daily(daily_fixture(), met_member())
    without = blend.combine_daily(daily_fixture())
    assert with_met["temperature_2m_max"][1] == without["temperature_2m_max"][1]


# ------------------------------------------------------- the visible spread

def hourly_fixture():
    return {
        "time": ["2026-08-20T14:00"],
        "apparent_temperature_ukmo_seamless": [18.6],
        "apparent_temperature_ecmwf_ifs025": [19.0],
        "apparent_temperature_icon_seamless": [19.1],
        "apparent_temperature_gfs_seamless": [18.1],
        "temperature_2m_ukmo_seamless": [21.4],
        "temperature_2m_ecmwf_ifs025": [21.6],
        "temperature_2m_icon_seamless": [21.3],
        "temperature_2m_gfs_seamless": [21.4],
    }


def test_every_member_reports_its_own_reading():
    members = blend.members_now(hourly_fixture(), "2026-08-20T14:07")
    assert [m["label"] for m in members] == [
        "Met Office UKV", "ECMWF IFS", "DWD ICON", "NOAA GFS"]
    assert members[0]["apparent_c"] == 18.6


def test_a_silent_member_is_left_out_not_zeroed():
    hourly = hourly_fixture()
    hourly["apparent_temperature_gfs_seamless"] = [None]
    hourly["temperature_2m_gfs_seamless"] = [None]
    members = blend.members_now(hourly, "2026-08-20T14:07")
    assert len(members) == 3


def test_the_datahub_current_reading_joins_the_row():
    members = blend.members_now(hourly_fixture(), "2026-08-20T14:07",
                                {"temp_c": 21.0, "apparent_c": 18.4})
    assert members[-1]["label"] == "Met Office DataHub"
    assert len(members) == 5


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
