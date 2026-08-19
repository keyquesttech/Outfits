"""Met Office DataHub Site Specific provider.

Endpoints and auth were verified against the live service:
  GET https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point/{hourly,three-hourly,daily}
      ?latitude=..&longitude=..
  Header: `apikey: <key>`   (a bad key returns 900901 "Invalid Credentials";
                             Authorization/Bearer returns 900902 "Missing Credentials")

Field names are read through candidate lists rather than hard-coded. The exact
spellings differ between the hourly, three-hourly and daily feeds, the full
schema sits behind a DataHub account, and a rename would otherwise silently
produce a forecast of nulls.
"""

import httpx

from .codes import METOFFICE, describe

BASE = "https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point"
TIMEOUT = 20

NAME = "metoffice"
LABEL = "Met Office"
NEEDS_KEY = True

# Free plan is a daily request allowance plus a monthly data volume, and caching
# is what keeps usage negligible. One refresh every five hours is about five
# calls a day; the refresh button on the Today page bypasses the cache whenever
# you actually want the latest reading.
REFRESH_SECONDS = 5 * 3600
FREE_TTL = REFRESH_SECONDS
NORMAL_TTL = REFRESH_SECONDS


class MetOfficeError(RuntimeError):
    pass


def _get(path: str, lat: float, lon: float, api_key: str) -> dict:
    url = f"{BASE}/{path}"
    headers = {"apikey": api_key, "Accept": "application/json"}
    params = {
        "latitude": lat,
        "longitude": lon,
        "excludeParameterMetadata": "true",   # smaller payload; counts against the data allowance
        "includeLocationName": "true",
    }
    with httpx.Client(timeout=TIMEOUT) as client:
        resp = client.get(url, headers=headers, params=params)
    if resp.status_code == 401:
        raise MetOfficeError("Met Office rejected the API key (401). Check it in Settings.")
    if resp.status_code == 403:
        raise MetOfficeError("Key is valid but not subscribed to Site Specific data (403).")
    if resp.status_code == 429:
        raise MetOfficeError("Met Office rate limit reached (429). "
                             "Turn on 'Optimise for the free plan' to cut request volume.")
    if resp.status_code >= 400:
        raise MetOfficeError(f"Met Office HTTP {resp.status_code}: {resp.text[:200]}")
    return resp.json()


def _series(payload: dict) -> list[dict]:
    for feature in payload.get("features") or []:
        series = (feature.get("properties") or {}).get("timeSeries")
        if series:
            return series
    return []


def _location_name(payload: dict) -> str | None:
    for feature in payload.get("features") or []:
        name = ((feature.get("properties") or {}).get("location") or {}).get("name")
        if name:
            return name
    return None


def pick(entry: dict, *names, default=None):
    """First present key wins. Guards against per-feed spelling differences."""
    for name in names:
        if entry.get(name) is not None:
            return entry[name]
    return default


def ms_to_kph(value):
    """Met Office reports wind in m/s; the rest of the app speaks km/h."""
    return None if value is None else round(value * 3.6, 1)


def _entry_time(entry: dict) -> str:
    return str(pick(entry, "time", "validTime", default=""))


def _nearest(series: list[dict], now_iso: str | None) -> dict:
    if not series:
        return {}
    if not now_iso:
        return series[0]
    future = [e for e in series if _entry_time(e) >= now_iso]
    return future[0] if future else series[-1]


def _condition(entry: dict, *names) -> dict:
    return describe(pick(entry, *names), METOFFICE)


def fetch(lat: float, lon: float, tz: str, api_key: str = "",
          optimize: bool = True, now_iso: str | None = None, **_) -> dict:
    if not api_key:
        raise MetOfficeError("No Met Office API key configured")

    from datetime import datetime, timezone as _tz
    now_iso = now_iso or datetime.now(_tz.utc).strftime("%Y-%m-%dT%H:%M")

    if optimize:
        # One request covers everything: three-hourly runs 168 hours, so it
        # supplies both the current conditions and the multi-day outlook.
        payload = _get("three-hourly", lat, lon, api_key)
        series = _series(payload)
        calls = 1
        detail_series = series
        days = _days_from_series(series)
        name = _location_name(payload)
    else:
        hourly = _get("hourly", lat, lon, api_key)
        daily = _get("daily", lat, lon, api_key)
        calls = 2
        detail_series = _series(hourly)
        days = _days_from_daily(_series(daily))
        name = _location_name(hourly) or _location_name(daily)

    if not detail_series:
        raise MetOfficeError("Met Office returned no forecast for that location")

    current_entry = _nearest(detail_series, now_iso)
    current = {
        "time": _entry_time(current_entry),
        "temp_c": pick(current_entry, "screenTemperature", "maxScreenAirTemp"),
        "apparent_c": pick(current_entry, "feelsLikeTemperature", "feelsLikeTemp"),
        "humidity": pick(current_entry, "screenRelativeHumidity"),
        "precipitation": pick(current_entry, "totalPrecipAmount", "precipitationRate"),
        "wind_kph": ms_to_kph(pick(current_entry, "windSpeed10m")),
        "condition": _condition(current_entry, "significantWeatherCode"),
    }

    return {
        "provider": NAME,
        "timezone": tz,
        "calls": calls,
        "site_name": name,
        "current": current,
        "today": _today(detail_series, days, now_iso),
        "daily": days[:5],
    }


def _day_of(entry: dict) -> str:
    return _entry_time(entry)[:10]


def _days_from_series(series: list[dict]) -> list[dict]:
    """Aggregate a sub-daily series into per-day summaries."""
    grouped: dict[str, list[dict]] = {}
    for entry in series:
        grouped.setdefault(_day_of(entry), []).append(entry)

    out = []
    for day in sorted(grouped):
        entries = grouped[day]
        temps = [pick(e, "screenTemperature", "maxScreenAirTemp") for e in entries]
        temps = [t for t in temps if t is not None]
        mins = [pick(e, "minScreenAirTemp", "screenTemperature") for e in entries]
        mins = [t for t in mins if t is not None]
        feels = [pick(e, "feelsLikeTemperature", "feelsLikeTemp") for e in entries]
        feels = [f for f in feels if f is not None]
        probs = [pick(e, "probOfPrecipitation", "probOfRain") for e in entries]
        probs = [p for p in probs if p is not None]
        winds = [pick(e, "windGustSpeed10m", "max10mWindGust", "windSpeed10m") for e in entries]
        winds = [w for w in winds if w is not None]
        # The midday entry best represents the day's headline condition.
        midday = min(entries, key=lambda e: abs(int(_entry_time(e)[11:13] or 12) - 12))
        out.append({
            "date": day,
            "max_c": max(temps) if temps else None,
            "min_c": min(mins) if mins else None,
            "apparent_max_c": max(feels) if feels else None,
            "apparent_min_c": min(feels) if feels else None,
            "rain_chance": max(probs) if probs else None,
            "wind_max_kph": ms_to_kph(max(winds)) if winds else None,
            "condition": _condition(midday, "significantWeatherCode"),
        })
    return out


def _days_from_daily(series: list[dict]) -> list[dict]:
    out = []
    for entry in series:
        out.append({
            "date": _entry_time(entry)[:10],
            "max_c": pick(entry, "dayMaxScreenTemperature", "maxScreenTemperature"),
            "min_c": pick(entry, "nightMinScreenTemperature", "minScreenTemperature"),
            "apparent_max_c": pick(entry, "dayMaxFeelsLikeTemp", "dayMaxFeelsLikeTemperature"),
            "apparent_min_c": pick(entry, "nightMinFeelsLikeTemp", "nightMinFeelsLikeTemperature"),
            "rain_chance": pick(entry, "dayProbabilityOfPrecipitation",
                                "probabilityOfPrecipitation"),
            "wind_max_kph": ms_to_kph(pick(entry, "midday10MWindSpeed", "midday10MWindGust")),
            "condition": _condition(entry, "daySignificantWeatherCode", "significantWeatherCode"),
        })
    return out


def _today(series: list[dict], days: list[dict], now_iso: str) -> dict:
    today = now_iso[:10]
    todays = [e for e in series if _day_of(e) == today]
    ahead = [e for e in todays if _entry_time(e) >= now_iso] or todays[-1:]

    def peak(entries):
        vals = [pick(e, "probOfPrecipitation", "probOfRain") for e in entries]
        vals = [v for v in vals if v is not None]
        return max(vals) if vals else None

    feels = [pick(e, "feelsLikeTemperature", "feelsLikeTemp") for e in ahead]
    feels = [f for f in feels if f is not None]
    summary = next((d for d in days if d["date"] == today), {})

    return {
        "date": today,
        "max_c": summary.get("max_c"),
        "min_c": summary.get("min_c"),
        "apparent_max_c": summary.get("apparent_max_c"),
        "apparent_min_c": summary.get("apparent_min_c"),
        # Same rule as Open-Meteo: only the hours still ahead can affect what you wear.
        "rain_chance": peak(ahead),
        "rain_chance_today": peak(todays),
        "wind_max_kph": summary.get("wind_max_kph"),
        "condition": summary.get("condition") or describe(None, METOFFICE),
        "apparent_range": [min(feels), max(feels)] if feels else None,
        "hours_remaining": len(ahead),
    }


def check(api_key: str = "", lat: float = 51.5072, lon: float = -0.1276, **_) -> dict:
    """Used by the Settings "Test connection" button."""
    if not api_key:
        return {"ok": False, "provider": LABEL, "error": "No API key entered"}
    try:
        payload = _get("hourly", lat, lon, api_key)
    except MetOfficeError as exc:
        return {"ok": False, "provider": LABEL, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "provider": LABEL, "error": f"{type(exc).__name__}: {exc}"}

    series = _series(payload)
    if not series:
        return {"ok": False, "provider": LABEL,
                "error": "Authenticated, but no timeSeries in the response"}
    first = series[0]
    temp = pick(first, "screenTemperature")
    feels = pick(first, "feelsLikeTemperature", "feelsLikeTemp")
    missing = [n for n, v in
               [("screenTemperature", temp), ("feelsLikeTemperature", feels),
                ("significantWeatherCode", pick(first, "significantWeatherCode")),
                ("probOfPrecipitation", pick(first, "probOfPrecipitation", "probOfRain"))]
               if v is None]
    return {
        "ok": True,
        "provider": LABEL,
        "site": _location_name(payload),
        "detail": f"{temp} °C, feels like {feels} °C, {len(series)} hourly steps",
        "fields_present": len(first),
        "missing_fields": missing,
    }
