"""Multi-model blend: several independent forecasts combined into one.

A consensus of models beats any single model — the disagreement between them is
real information, and the median of several is more accurate than the best one
alone. That is standard forecasting practice, and it is available here for free:
one keyless Open-Meteo request returns four independent models side by side —
the Met Office's own UKV, ECMWF's IFS, DWD's ICON and NOAA's GFS — and when a
Met Office DataHub key is saved, the DataHub feed joins as a fifth member.

Combining rules, chosen for the way each quantity behaves:
- temperatures and wind: median. Robust — one model having a bad day cannot
  drag the answer.
- rain chance: mean. Averaging probabilities across models is what makes them
  honest; the median of {28, 77, 35} throws information away.
- condition: the group most models agree on.

The spread between members is kept and shown, because "the models disagree by
four degrees" is worth knowing before trusting any number.
"""

import httpx

from . import metoffice, openmeteo
from .codes import describe

API = openmeteo.API
TIMEOUT = 20

NAME = "blend"
LABEL = "Blend"
NEEDS_KEY = False

# The independent members. best_match is requested too, but only as a fallback
# for condition codes — for London it *is* UKMO, and letting it vote as well
# would count the same model twice.
MODELS = [
    ("ukmo_seamless", "Met Office UKV"),
    ("ecmwf_ifs025", "ECMWF IFS"),
    ("icon_seamless", "DWD ICON"),
    ("gfs_seamless", "NOAA GFS"),
]
METOFFICE_MEMBER = "Met Office DataHub"

DAILY_FIELDS = ("weather_code", "temperature_2m_max", "temperature_2m_min",
                "apparent_temperature_max", "apparent_temperature_min",
                "precipitation_probability_max", "wind_speed_10m_max")

# Met Office daily entries, mapped onto the same field names.
_MET_DAILY = {
    "temperature_2m_max": "max_c",
    "temperature_2m_min": "min_c",
    "apparent_temperature_max": "apparent_max_c",
    "apparent_temperature_min": "apparent_min_c",
    "precipitation_probability_max": "rain_chance",
    "wind_speed_10m_max": "wind_max_kph",
}


def median(values):
    """Median of the non-null values, or None when there are none."""
    kept = sorted(v for v in values if v is not None)
    if not kept:
        return None
    mid = len(kept) // 2
    if len(kept) % 2:
        return kept[mid]
    return (kept[mid - 1] + kept[mid]) / 2


def mean(values):
    kept = [v for v in values if v is not None]
    return sum(kept) / len(kept) if kept else None


def majority_code(codes, fallback=None):
    """The weather code whose condition group most members voted for."""
    groups: dict[str, list] = {}
    for code in codes:
        if code is None:
            continue
        groups.setdefault((describe(code) or {}).get("group"), []).append(code)
    if not groups:
        return fallback
    best = max(groups.values(), key=len)
    if fallback is not None and len(best) <= 1 and len(groups) > 1:
        return fallback            # no consensus: trust the locally-best model
    return best[0]


def _series(block: dict, field: str, model: str) -> list:
    return block.get(f"{field}_{model}") or []


def _at(seq, i):
    return seq[i] if seq and i < len(seq) else None


def combine_daily(daily: dict, met_by_date: dict | None = None) -> dict:
    """Fold the per-model series into one, in Open-Meteo's own field names.

    Producing the raw shape rather than a new one lets the blend reuse the
    Open-Meteo provider's `_today` and `_daily` unchanged.
    """
    times = daily.get("time") or []
    met_by_date = met_by_date or {}
    out: dict = {"time": times}
    for field in DAILY_FIELDS:
        combined = []
        for i, day in enumerate(times):
            votes = [_at(_series(daily, field, model), i) for model, _ in MODELS]
            met_day = met_by_date.get(day)
            if field == "weather_code":
                fallback = _at(_series(daily, field, "best_match"), i)
                if met_day and (met_day.get("condition") or {}).get("code") is not None:
                    votes.append(met_day["condition"]["code"])
                combined.append(majority_code(votes, fallback))
                continue
            if met_day and _MET_DAILY.get(field):
                votes.append(met_day.get(_MET_DAILY[field]))
            if field == "precipitation_probability_max":
                value = mean(votes)
                combined.append(round(value) if value is not None else None)
            else:
                value = median(votes)
                combined.append(round(value, 1) if value is not None else None)
        out[field] = combined
    return out


def combine_hourly(hourly: dict) -> dict:
    """One consensus hourly series, for the still-ahead-today arithmetic."""
    times = hourly.get("time") or []
    apparent, probability = [], []
    for i in range(len(times)):
        apparent.append(median(
            [_at(_series(hourly, "apparent_temperature", m), i) for m, _ in MODELS]))
        value = mean(
            [_at(_series(hourly, "precipitation_probability", m), i) for m, _ in MODELS])
        probability.append(round(value) if value is not None else None)
    return {"time": times,
            "apparent_temperature": apparent,
            "precipitation_probability": probability}


def members_now(hourly: dict, now_iso: str | None, met_current: dict | None = None) -> list[dict]:
    """Each member's reading for the current hour — the visible disagreement."""
    times = hourly.get("time") or []
    idx = None
    if now_iso:
        hour = str(now_iso)[:13] + ":00"
        idx = times.index(hour) if hour in times else None
    if idx is None and times:
        idx = 0

    out = []
    for model, label in MODELS:
        apparent = _at(_series(hourly, "apparent_temperature", model), idx)
        temp = _at(_series(hourly, "temperature_2m", model), idx)
        if apparent is None and temp is None:
            continue
        out.append({"name": model, "label": label,
                    "temp_c": temp, "apparent_c": apparent})
    if met_current and met_current.get("apparent_c") is not None:
        out.append({"name": "metoffice", "label": METOFFICE_MEMBER,
                    "temp_c": met_current.get("temp_c"),
                    "apparent_c": met_current.get("apparent_c")})
    return out


def fetch(lat: float, lon: float, tz: str, api_key: str = "", **_) -> dict:
    params = {
        "latitude": lat, "longitude": lon, "timezone": tz,
        "forecast_days": 5,
        "models": "best_match," + ",".join(m for m, _ in MODELS),
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,"
                   "precipitation,weather_code,wind_speed_10m",
        "hourly": "temperature_2m,apparent_temperature,precipitation_probability",
        "daily": ",".join(DAILY_FIELDS),
    }
    with httpx.Client(timeout=TIMEOUT) as client:
        raw = client.get(API, params=params).raise_for_status().json()

    cur = raw.get("current") or {}
    hourly = raw.get("hourly") or {}
    daily = raw.get("daily") or {}

    # The DataHub feed joins as a member when a key is saved. Its failure is a
    # thinner blend, never a failed forecast.
    met, met_calls = None, 0
    if api_key:
        try:
            met = metoffice.fetch(lat, lon, tz, api_key=api_key, optimize=True)
            met_calls = met.get("calls", 1)
        except Exception:
            met = None
    met_by_date = {d["date"]: d for d in (met or {}).get("daily", []) if d.get("date")}
    met_current = (met or {}).get("current")

    members = members_now(hourly, cur.get("time"), met_current)
    apparents = [m["apparent_c"] for m in members if m["apparent_c"] is not None]
    spread = round(max(apparents) - min(apparents), 1) if len(apparents) > 1 else 0.0

    combined_daily = combine_daily(daily, met_by_date)
    combined_hourly = combine_hourly(hourly)
    today = openmeteo._today(combined_daily, combined_hourly, cur.get("time"))
    days = openmeteo._daily(combined_daily)

    current = {
        "time": cur.get("time"),
        "temp_c": median([m["temp_c"] for m in members]) or cur.get("temperature_2m"),
        "apparent_c": median(apparents) if apparents else cur.get("apparent_temperature"),
        # Humidity and falling-now precipitation come from the locally best
        # model; the members were not asked for them to keep the payload small.
        "humidity": cur.get("relative_humidity_2m"),
        "precipitation": cur.get("precipitation"),
        "wind_kph": cur.get("wind_speed_10m"),
        "condition": describe(cur.get("weather_code")),
    }
    if met_current and met_current.get("wind_kph") is not None:
        current["wind_kph"] = median([cur.get("wind_speed_10m"),
                                      met_current["wind_kph"]])

    return {
        "provider": NAME,
        "timezone": raw.get("timezone", tz),
        "calls": 1,
        "metoffice_calls": met_calls,
        "current": current,
        "today": today,
        "daily": days,
        "blend": {
            "members": members,
            "member_count": len(members),
            "spread_c": spread,
            "with_metoffice": bool(met),
        },
    }


def check(api_key: str = "", lat: float = 51.5072, lon: float = -0.1276, **_) -> dict:
    try:
        data = fetch(lat, lon, "Europe/London", api_key=api_key)
    except Exception as exc:
        return {"ok": False, "provider": LABEL, "error": str(exc)}
    members = data["blend"]["members"]
    return {
        "ok": bool(members),
        "provider": LABEL,
        "temp_c": data["current"].get("temp_c"),
        "apparent_c": data["current"].get("apparent_c"),
        "members": [m["label"] for m in members],
        "spread_c": data["blend"]["spread_c"],
        "note": (f"{len(members)} models answered, agreeing within "
                 f"{data['blend']['spread_c']}° on feels-like."
                 + ("" if data["blend"]["with_metoffice"] else
                    " Save a Met Office key and the DataHub feed joins the blend.")),
    }
