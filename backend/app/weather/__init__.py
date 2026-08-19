"""Weather layer: provider selection, caching, and usage accounting.

Both providers return the same normalised shape, so nothing downstream — the
recommender, the wear log, the UI — needs to know which service supplied it.
"""

import time

from .. import db
from . import metoffice, openmeteo, warnings
from .codes import describe  # re-exported; callers still do weather.describe(...)

PROVIDERS = {
    openmeteo.NAME: openmeteo,
    metoffice.NAME: metoffice,
}

DEFAULT_TTL = 1800

_cache: dict = {"at": 0.0, "key": None, "data": None}

__all__ = ["fetch", "describe", "geocode", "check", "warnings", "PROVIDERS", "provider_info"]


def _settings() -> dict:
    return {
        "provider": db.get_setting("weather_provider", openmeteo.NAME) or openmeteo.NAME,
        "lat": float(db.get_setting("latitude", "51.5072") or 51.5072),
        "lon": float(db.get_setting("longitude", "-0.1276") or -0.1276),
        "tz": db.get_setting("timezone", "Europe/London") or "Europe/London",
        "name": db.get_setting("location_name", "London, UK"),
        "metoffice_key": db.get_setting("metoffice_api_key", ""),
        "optimize": db.get_setting("metoffice_optimize", "1") != "0",
        "warnings_on": db.get_setting("warnings_enabled", "1") != "0",
        "warnings_region": db.get_setting("warnings_region", "uk") or "uk",
    }


def _ttl(cfg: dict) -> int:
    if cfg["provider"] == metoffice.NAME:
        return metoffice.FREE_TTL if cfg["optimize"] else metoffice.NORMAL_TTL
    return DEFAULT_TTL


def _count_call(provider: str, calls: int) -> None:
    """Track Met Office usage so the free allowance is visible, not guesswork."""
    if provider != metoffice.NAME or calls <= 0:
        return
    month = time.strftime("%Y-%m")
    if db.get_setting("metoffice_usage_month", "") != month:
        db.set_setting("metoffice_usage_month", month)
        db.set_setting("metoffice_usage_calls", "0")
    total = int(db.get_setting("metoffice_usage_calls", "0") or 0) + calls
    db.set_setting("metoffice_usage_calls", str(total))
    db.set_setting("metoffice_last_call", str(int(time.time())))


def usage() -> dict:
    month = time.strftime("%Y-%m")
    stored_month = db.get_setting("metoffice_usage_month", "")
    calls = int(db.get_setting("metoffice_usage_calls", "0") or 0) if stored_month == month else 0
    optimize = db.get_setting("metoffice_optimize", "1") != "0"
    ttl = metoffice.FREE_TTL if optimize else metoffice.NORMAL_TTL
    per_refresh = 1 if optimize else 2
    projected = round((86400 / ttl) * per_refresh * 30)
    return {
        "month": month,
        "calls": calls,
        "optimize": optimize,
        "cache_ttl_seconds": ttl,
        "calls_per_refresh": per_refresh,
        "projected_monthly_calls": projected,
        "note": (
            f"At most one refresh every {ttl // 3600} h, "
            f"{per_refresh} call{'s' if per_refresh > 1 else ''} each — "
            f"about {projected} calls a month."
        ),
    }


def fetch(force: bool = False) -> dict:
    cfg = _settings()
    module = PROVIDERS.get(cfg["provider"], openmeteo)
    key = f"{module.NAME}:{cfg['lat']},{cfg['lon']},{cfg['tz']},{cfg['optimize']}"
    now = time.time()

    if not force and _cache["data"] and _cache["key"] == key and now - _cache["at"] < _ttl(cfg):
        return _with_warnings(dict(_cache["data"]), cfg)

    try:
        raw = module.fetch(
            cfg["lat"], cfg["lon"], cfg["tz"],
            api_key=cfg["metoffice_key"], optimize=cfg["optimize"],
        )
        _count_call(module.NAME, raw.get("calls", 0))
    except Exception as exc:
        # A configuration mistake should degrade to the last good forecast, or to
        # a clear message — never to a blank page.
        if _cache["data"] and _cache["key"] == key:
            stale = dict(_cache["data"])
            stale.update({"stale": True, "error": str(exc)})
            return _with_warnings(stale, cfg)
        return _with_warnings({
            "available": False,
            "error": str(exc),
            "provider": module.NAME,
            "provider_label": getattr(module, "LABEL", module.NAME),
            "location": cfg["name"],
        }, cfg)

    data = {
        "available": True,
        "stale": False,
        "location": raw.get("site_name") or cfg["name"],
        "provider": module.NAME,
        "provider_label": getattr(module, "LABEL", module.NAME),
        "fetched_at": now,
        **{k: v for k, v in raw.items() if k not in ("provider", "calls", "site_name")},
    }
    _cache.update({"at": now, "key": key, "data": data})
    return _with_warnings(dict(data), cfg)


def _with_warnings(data: dict, cfg: dict) -> dict:
    if cfg["warnings_on"]:
        data["warnings"] = warnings.fetch(cfg["warnings_region"])
    else:
        data["warnings"] = {"available": False, "disabled": True, "warnings": []}
    return data


def geocode(query: str, count: int = 6) -> list[dict]:
    """Place-name lookup, always via Open-Meteo — free and keyless regardless of
    which forecast provider is in use."""
    return openmeteo.geocode(query, count)


def check(provider: str | None = None, api_key: str | None = None) -> dict:
    cfg = _settings()
    name = provider or cfg["provider"]
    module = PROVIDERS.get(name, openmeteo)
    key = api_key if api_key is not None else cfg["metoffice_key"]
    return module.check(api_key=key, lat=cfg["lat"], lon=cfg["lon"])


def provider_info() -> list[dict]:
    return [
        {
            "name": m.NAME,
            "label": m.LABEL,
            "needs_key": m.NEEDS_KEY,
            "description": (
                "Free and keyless. Global coverage, no account needed."
                if m.NAME == openmeteo.NAME else
                "UK forecasts from the Met Office. Needs a free DataHub API key."
            ),
        }
        for m in (openmeteo, metoffice)
    ]
