"""Open-Meteo client. Free, keyless, and reachable from inside the namespace.

`apparent_temperature` (feels-like) is what the recommender scores against —
it already folds in wind chill and humidity, which raw air temperature does not.
"""

import time

import httpx

from . import db

API = "https://api.open-meteo.com/v1/forecast"
CACHE_TTL = 1800  # half an hour; Open-Meteo updates every 15 min

_cache: dict = {"at": 0.0, "key": None, "data": None}

WMO = {
    0: ("Clear", "clear"), 1: ("Mainly clear", "clear"), 2: ("Partly cloudy", "cloud"),
    3: ("Overcast", "cloud"), 45: ("Fog", "fog"), 48: ("Rime fog", "fog"),
    51: ("Light drizzle", "rain"), 53: ("Drizzle", "rain"), 55: ("Heavy drizzle", "rain"),
    56: ("Freezing drizzle", "rain"), 57: ("Freezing drizzle", "rain"),
    61: ("Light rain", "rain"), 63: ("Rain", "rain"), 65: ("Heavy rain", "rain"),
    66: ("Freezing rain", "rain"), 67: ("Freezing rain", "rain"),
    71: ("Light snow", "snow"), 73: ("Snow", "snow"), 75: ("Heavy snow", "snow"),
    77: ("Snow grains", "snow"), 80: ("Light showers", "rain"), 81: ("Showers", "rain"),
    82: ("Violent showers", "rain"), 85: ("Snow showers", "snow"), 86: ("Snow showers", "snow"),
    95: ("Thunderstorm", "storm"), 96: ("Thunderstorm with hail", "storm"),
    99: ("Thunderstorm with hail", "storm"),
}


def describe(code) -> dict:
    label, group = WMO.get(int(code) if code is not None else -1, ("Unknown", "cloud"))
    return {"code": code, "label": label, "group": group}


def _location() -> tuple[float, float, str, str]:
    lat = float(db.get_setting("latitude", "51.5072") or 51.5072)
    lon = float(db.get_setting("longitude", "-0.1276") or -0.1276)
    tz = db.get_setting("timezone", "Europe/London") or "Europe/London"
    name = db.get_setting("location_name", "London, UK")
    return lat, lon, tz, name


def fetch(force: bool = False) -> dict:
    lat, lon, tz, name = _location()
    key = f"{lat},{lon},{tz}"
    now = time.time()
    if not force and _cache["data"] and _cache["key"] == key and now - _cache["at"] < CACHE_TTL:
        return _cache["data"]

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
    try:
        with httpx.Client(timeout=12) as client:
            raw = client.get(API, params=params).raise_for_status().json()
    except Exception as exc:
        if _cache["data"]:  # serve stale rather than break the page
            stale = dict(_cache["data"])
            stale["stale"] = True
            stale["error"] = str(exc)
            return stale
        return {"available": False, "error": str(exc), "location": name}

    cur = raw.get("current", {}) or {}
    daily = raw.get("daily", {}) or {}
    hourly = raw.get("hourly", {}) or {}

    data = {
        "available": True,
        "stale": False,
        "location": name,
        "timezone": raw.get("timezone", tz),
        "fetched_at": now,
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
    _cache.update({"at": now, "key": key, "data": data})
    return data


def _today(daily: dict, hourly: dict, now_iso: str | None = None) -> dict:
    """Today's outlook, scored over the hours that are still ahead.

    Taking the maximum across the whole calendar day is misleading once the day
    is under way: a 100% chance at 4am would otherwise report as "100% rain" at
    teatime under clear skies, and push the recommender into a raincoat.
    """
    times = hourly.get("time", []) or []
    probs = hourly.get("precipitation_probability", []) or []
    apparent = hourly.get("apparent_temperature", []) or []
    today = (daily.get("time") or [None])[0]

    today_idx = [i for i, t in enumerate(times) if today and str(t).startswith(str(today))]
    ahead_idx = [i for i in today_idx if not now_iso or str(times[i]) >= str(now_iso)[:13]]
    if not ahead_idx:  # late evening, nothing left today
        ahead_idx = today_idx[-1:]

    def peak(seq, idx):
        return max((seq[i] for i in idx if i < len(seq)), default=None)

    remaining = [apparent[i] for i in ahead_idx if i < len(apparent)]
    return {
        "date": today,
        "max_c": (daily.get("temperature_2m_max") or [None])[0],
        "min_c": (daily.get("temperature_2m_min") or [None])[0],
        "apparent_max_c": (daily.get("apparent_temperature_max") or [None])[0],
        "apparent_min_c": (daily.get("apparent_temperature_min") or [None])[0],
        "rain_chance": peak(probs, ahead_idx),
        "rain_chance_today": peak(probs, today_idx),
        "wind_max_kph": (daily.get("wind_speed_10m_max") or [None])[0],
        "condition": describe((daily.get("weather_code") or [None])[0]),
        "apparent_range": [min(remaining), max(remaining)] if remaining else None,
        "hours_remaining": len(ahead_idx),
    }


def _daily(daily: dict) -> list[dict]:
    out = []
    for i, day in enumerate(daily.get("time", []) or []):
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
