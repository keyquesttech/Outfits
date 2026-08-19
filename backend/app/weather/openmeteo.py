"""Open-Meteo provider. Free, keyless, no account."""

import httpx

from .codes import describe

API = "https://api.open-meteo.com/v1/forecast"
GEOCODE = "https://geocoding-api.open-meteo.com/v1/search"
TIMEOUT = 15

NAME = "open-meteo"
LABEL = "Open-Meteo"
NEEDS_KEY = False


def fetch(lat: float, lon: float, tz: str, **_) -> dict:
    params = {
        "latitude": lat,
        "longitude": lon,
        "timezone": tz,
        "forecast_days": 5,
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,"
                   "precipitation,weather_code,wind_speed_10m",
        "hourly": "temperature_2m,apparent_temperature,precipitation_probability,weather_code",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                 "apparent_temperature_max,apparent_temperature_min,"
                 "precipitation_probability_max,wind_speed_10m_max",
    }
    with httpx.Client(timeout=TIMEOUT) as client:
        raw = client.get(API, params=params).raise_for_status().json()

    cur = raw.get("current") or {}
    daily = raw.get("daily") or {}
    hourly = raw.get("hourly") or {}

    return {
        "provider": NAME,
        "timezone": raw.get("timezone", tz),
        "calls": 1,
        "current": {
            "time": cur.get("time"),
            "temp_c": cur.get("temperature_2m"),
            "apparent_c": cur.get("apparent_temperature"),
            "humidity": cur.get("relative_humidity_2m"),
            "precipitation": cur.get("precipitation"),
            "wind_kph": cur.get("wind_speed_10m"),
            "condition": describe(cur.get("weather_code")),
        },
        "today": _today(daily, hourly, cur.get("time")),
        "daily": _daily(daily),
    }


def _today(daily: dict, hourly: dict, now_iso: str | None) -> dict:
    """Today's outlook, scored over the hours still ahead.

    Taking the maximum across the whole calendar day is misleading once the day
    is under way: a 100% chance at 4am would otherwise report as "100% rain" at
    teatime under clear skies, and push the recommender into a raincoat.
    """
    times = hourly.get("time") or []
    probs = hourly.get("precipitation_probability") or []
    apparent = hourly.get("apparent_temperature") or []
    today = (daily.get("time") or [None])[0]

    today_idx = [i for i, t in enumerate(times) if today and str(t).startswith(str(today))]
    ahead_idx = [i for i in today_idx if not now_iso or str(times[i]) >= str(now_iso)[:13]]
    if not ahead_idx:
        ahead_idx = today_idx[-1:]

    def peak(seq, idx):
        return max((seq[i] for i in idx if i < len(seq)), default=None)

    remaining = [apparent[i] for i in ahead_idx if i < len(apparent)]
    return {
        "date": today,
        "max_c": _at(daily.get("temperature_2m_max"), 0),
        "min_c": _at(daily.get("temperature_2m_min"), 0),
        "apparent_max_c": _at(daily.get("apparent_temperature_max"), 0),
        "apparent_min_c": _at(daily.get("apparent_temperature_min"), 0),
        "rain_chance": peak(probs, ahead_idx),
        "rain_chance_today": peak(probs, today_idx),
        "wind_max_kph": _at(daily.get("wind_speed_10m_max"), 0),
        "condition": describe(_at(daily.get("weather_code"), 0)),
        "apparent_range": [min(remaining), max(remaining)] if remaining else None,
        "hours_remaining": len(ahead_idx),
    }


def _daily(daily: dict) -> list[dict]:
    out = []
    for i, day in enumerate(daily.get("time") or []):
        out.append({
            "date": day,
            "max_c": _at(daily.get("temperature_2m_max"), i),
            "min_c": _at(daily.get("temperature_2m_min"), i),
            "apparent_max_c": _at(daily.get("apparent_temperature_max"), i),
            "apparent_min_c": _at(daily.get("apparent_temperature_min"), i),
            "rain_chance": _at(daily.get("precipitation_probability_max"), i),
            "wind_max_kph": _at(daily.get("wind_speed_10m_max"), i),
            "condition": describe(_at(daily.get("weather_code"), i)),
        })
    return out


def _at(seq, i):
    return seq[i] if seq and i < len(seq) else None


def geocode(query: str, count: int = 6) -> list[dict]:
    """Place-name search. Also free and keyless, and useful whichever forecast
    provider is selected."""
    with httpx.Client(timeout=TIMEOUT) as client:
        raw = client.get(GEOCODE, params={
            "name": query, "count": count, "language": "en", "format": "json",
        }).raise_for_status().json()
    out = []
    for r in raw.get("results") or []:
        parts = [r.get("name"), r.get("admin1"), r.get("country")]
        out.append({
            "name": r.get("name"),
            "label": ", ".join(p for p in parts if p),
            "latitude": r.get("latitude"),
            "longitude": r.get("longitude"),
            "timezone": r.get("timezone"),
            "country_code": r.get("country_code"),
        })
    return out


def check(**_) -> dict:
    try:
        data = fetch(51.5072, -0.1276, "Europe/London")
        return {"ok": True, "provider": LABEL,
                "detail": f"{data['current']['temp_c']} °C, {data['current']['condition']['label']}"}
    except Exception as exc:
        return {"ok": False, "provider": LABEL, "error": str(exc)}
