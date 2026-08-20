"""Weather for a day that has already happened.

Back-dating a wear is only useful if the weather goes back with it. The comfort
calibration learns from the gap between how warm an outfit was and how warm the
day actually was, so stamping today's 17 °C on an outfit worn last Tuesday would
teach it something false.

Open-Meteo serves both halves of this for free with no key: the forecast
endpoint carries up to 92 days of past days alongside the forecast, and the
archive endpoint goes back decades. Days are cached, because a day that has
already happened does not change — and a whole window is fetched at once, so
back-dating a week of outfits costs one request rather than seven.
"""

from datetime import date, timedelta

import httpx

from .. import db
from .codes import describe

FORECAST_API = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_API = "https://archive-api.open-meteo.com/v1/archive"
TIMEOUT = 20

# The forecast endpoint advertises 92 past days, but the readings thin out to
# nulls well before that and the exact point moves. So this is only which source
# to *try first*: if the day comes back empty, the other one is asked. Guessing a
# threshold and trusting it is what left an 80-day-old day silently blank.
RECENT_DAYS = 30
# The archive lags real time by about five days, so anything newer has to come
# from the forecast endpoint whatever the gap says.
ARCHIVE_LAG_DAYS = 6
# Days fetched either side of the one asked for, so filling in a week of
# back-dated outfits is one call rather than seven.
WINDOW = 10

DAILY_FIELDS = ("weather_code,temperature_2m_max,temperature_2m_min,"
                "apparent_temperature_max,apparent_temperature_min,"
                "wind_speed_10m_max")


def _key(lat: float, lon: float) -> tuple[float, float]:
    """Round the place, so a GPS jitter of a few metres is not a cache miss."""
    return (round(float(lat), 2), round(float(lon), 2))


def _row_out(row: dict) -> dict:
    return {
        "date": row["day"],
        "temp_c": row["temp_c"],
        "apparent_c": row["apparent_c"],
        "rain_chance": row["rain_chance"],
        "wind_kph": row["wind_kph"],
        "condition": describe(row["code"]) if row["code"] is not None else None,
        "available": row["apparent_c"] is not None,
    }


def cached(day: str, lat: float, lon: float) -> dict | None:
    rlat, rlon = _key(lat, lon)
    row = db.query_one(
        "SELECT * FROM weather_days WHERE day = ? AND lat = ? AND lon = ?",
        (day, rlat, rlon))
    return _row_out(row) if row else None


def _store(days: list[dict], lat: float, lon: float) -> None:
    """Cache the days that actually carry a reading.

    A source that answers with nulls for a day must not overwrite a good row
    that another source already filled in.
    """
    rlat, rlon = _key(lat, lon)
    days = [d for d in days if d["apparent_c"] is not None or d["temp_c"] is not None]
    if not days:
        return
    db.executemany(
        "INSERT INTO weather_days(day, lat, lon, temp_c, apparent_c, rain_chance, "
        "wind_kph, code, condition, fetched_at) VALUES (?,?,?,?,?,?,?,?,?,datetime('now')) "
        "ON CONFLICT(day, lat, lon) DO UPDATE SET temp_c=excluded.temp_c, "
        "apparent_c=excluded.apparent_c, rain_chance=excluded.rain_chance, "
        "wind_kph=excluded.wind_kph, code=excluded.code, condition=excluded.condition, "
        "fetched_at=datetime('now')",
        [(d["day"], rlat, rlon, d["temp_c"], d["apparent_c"], d["rain_chance"],
          d["wind_kph"], d["code"],
          (describe(d["code"]) or {}).get("label") if d["code"] is not None else None)
         for d in days],
    )


def _mean(a, b):
    values = [v for v in (a, b) if v is not None]
    return sum(values) / len(values) if values else None


def _parse(daily: dict) -> list[dict]:
    """A day is summarised by its midpoint, which is what a wear is scored on."""
    out = []
    for i, day in enumerate(daily.get("time") or []):
        def at(field):
            seq = daily.get(field) or []
            return seq[i] if i < len(seq) else None

        out.append({
            "day": day,
            "temp_c": _mean(at("temperature_2m_max"), at("temperature_2m_min")),
            "apparent_c": _mean(at("apparent_temperature_max"),
                                at("apparent_temperature_min")),
            "rain_chance": at("precipitation_probability_max"),
            "wind_kph": at("wind_speed_10m_max"),
            "code": at("weather_code"),
        })
    return out


def _from_forecast(day: date, lat: float, lon: float, tz: str) -> list[dict]:
    """Recent past, from the forecast endpoint. It alone reports rain chance."""
    age = (date.today() - day).days
    return _get(FORECAST_API, {
        "latitude": lat, "longitude": lon, "timezone": tz,
        "past_days": min(92, max(1, age + WINDOW)),
        "forecast_days": 1,
        "daily": DAILY_FIELDS + ",precipitation_probability_max",
    })


def _from_archive(day: date, lat: float, lon: float, tz: str) -> list[dict]:
    """Anything older. Goes back decades, but lags real time by a few days."""
    today = date.today()
    end = min(day + timedelta(days=WINDOW), today - timedelta(days=ARCHIVE_LAG_DAYS))
    if end < day:
        return []
    return _get(ARCHIVE_API, {
        "latitude": lat, "longitude": lon, "timezone": tz,
        "start_date": (day - timedelta(days=WINDOW)).isoformat(),
        "end_date": end.isoformat(),
        "daily": DAILY_FIELDS,
    })


def _get(url: str, params: dict) -> list[dict]:
    with httpx.Client(timeout=TIMEOUT) as client:
        raw = client.get(url, params=params).raise_for_status().json()
    return _parse(raw.get("daily") or {})


def _has(days: list[dict], day: str) -> bool:
    return any(d["day"] == day and d["apparent_c"] is not None for d in days)


def _fetch_window(day: date, lat: float, lon: float, tz: str) -> list[dict]:
    """Ask the likelier source first, and the other one if it comes back empty."""
    wanted = day.isoformat()
    recent_first = (date.today() - day).days <= RECENT_DAYS
    order = ([_from_forecast, _from_archive] if recent_first
             else [_from_archive, _from_forecast])

    collected: list[dict] = []
    for source in order:
        try:
            days = source(day, lat, lon, tz)
        except Exception:
            continue
        collected += days
        if _has(days, wanted):
            break
    return collected


def for_date(day: str, force: bool = False) -> dict:
    """The weather on one past day, from cache where possible.

    A day in the future has no history to look up — the forecast covers that,
    and this returns "unavailable" rather than inventing something.
    """
    try:
        wanted = date.fromisoformat(day)
    except ValueError:
        return {"date": day, "available": False, "reason": "Not a date"}

    lat = float(db.get_setting("latitude", "51.5072") or 51.5072)
    lon = float(db.get_setting("longitude", "-0.1276") or -0.1276)
    tz = db.get_setting("timezone", "Europe/London") or "Europe/London"

    if wanted > date.today():
        return {"date": day, "available": False,
                "reason": "That day has not happened yet"}

    if not force:
        hit = cached(day, lat, lon)
        if hit:
            return {**hit, "source": "cache"}

    try:
        days = _fetch_window(wanted, lat, lon, tz)
    except Exception as exc:
        return {"date": day, "available": False, "reason": f"Lookup failed: {exc}"}

    if days:
        _store(days, lat, lon)
    hit = cached(day, lat, lon)
    if hit and hit["available"]:
        return {**hit, "source": "fetched"}
    return {"date": day, "available": False,
            "reason": "No reading for that day"}
