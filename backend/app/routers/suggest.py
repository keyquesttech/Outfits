from fastapi import APIRouter, HTTPException, Query

from .. import db, recommend, weather
from ..ai import get_provider
from ..models import SuggestIn, WeatherTestIn
from ..serializers import item_out, load_items

router = APIRouter(prefix="/api", tags=["suggest"])


@router.get("/weather")
def get_weather(refresh: bool = False):
    return weather.fetch(force=refresh)


@router.get("/weather/providers")
def weather_providers():
    return {
        "providers": weather.provider_info(),
        "current": db.get_setting("weather_provider", "open-meteo"),
        "usage": weather.usage(),
    }


@router.post("/weather/test")
def weather_test(payload: WeatherTestIn):
    """Check a provider before committing to it. An API key can be passed in so
    the key is validated before it is saved."""
    return weather.check(payload.provider, payload.api_key)


@router.get("/weather/usage")
def weather_usage():
    return weather.usage()


@router.get("/weather/warnings")
def weather_warnings(region: str | None = None, refresh: bool = False,
                     today_only: bool = True):
    """Region defaults to whichever one covers the configured location."""
    if not region:
        lat = float(db.get_setting("latitude", "51.5072") or 51.5072)
        lon = float(db.get_setting("longitude", "-0.1276") or -0.1276)
        derived = weather.warnings.region_for(lat, lon)
        if not derived["in_uk"]:
            raise HTTPException(
                400, "Met Office warnings only cover the UK, and the configured "
                     "location is outside it.")
        region = derived["code"]
    return weather.warnings.fetch(region, force=refresh, today_only=today_only)


@router.get("/geoip")
def geoip(refresh: bool = False):
    """Approximate location from the public IP.

    Browsers block GPS on insecure origins, so this is the fallback that works
    over plain HTTP on the LAN with no permission prompt.
    """
    result = weather.locate_by_ip(force=refresh)
    if not result.get("available"):
        raise HTTPException(502, result.get("message", "Location lookup failed"))
    return result


@router.get("/geocode")
def geocode(q: str = Query(..., min_length=2, max_length=120)):
    """Place-name search, so the location can be set without knowing coordinates."""
    try:
        return {"results": weather.geocode(q)}
    except Exception as exc:
        raise HTTPException(502, f"Place lookup failed: {exc}") from exc


def _conditions(day_offset: int) -> dict:
    data = weather.fetch()
    if not data.get("available"):
        return {"apparent_c": None, "rain_chance": None, "wind_kph": None,
                "summary": "weather unavailable", "available": False}
    if day_offset == 0:
        current = data.get("current") or {}
        today = data.get("today") or {}
        return {
            "apparent_c": current.get("apparent_c"),
            "rain_chance": today.get("rain_chance"),
            "wind_kph": current.get("wind_kph"),
            "condition": current.get("condition"),
            "summary": f"{(current.get('condition') or {}).get('label', '')}, "
                       f"feels like {current.get('apparent_c')} °C, "
                       f"{today.get('rain_chance') or 0}% rain",
            "available": True,
        }
    days = data.get("daily") or []
    day = days[min(day_offset, len(days) - 1)] if days else {}
    highs = [v for v in (day.get("apparent_max_c"), day.get("apparent_min_c")) if v is not None]
    apparent = sum(highs) / len(highs) if highs else None
    return {
        "apparent_c": apparent,
        "rain_chance": day.get("rain_chance"),
        "wind_kph": day.get("wind_max_kph"),
        "condition": day.get("condition"),
        "date": day.get("date"),
        "summary": f"{(day.get('condition') or {}).get('label', '')} on {day.get('date')}, "
                   f"feels like {apparent:.0f} °C" if apparent is not None else "forecast",
        "available": True,
    }


@router.post("/suggest")
def suggest(payload: SuggestIn):
    conditions = _conditions(payload.day_offset)
    result = recommend.suggest(
        conditions,
        occasion=payload.occasion,
        count=payload.count,
        exclude_dirty=payload.exclude_dirty,
        seasons=payload.seasons,
        pinned=payload.pinned,
    )
    result["weather"] = conditions

    if payload.use_ai:
        result["ai"] = _ai_suggestion(conditions, payload)
    return result


def _ai_suggestion(conditions: dict, payload: SuggestIn) -> dict:
    provider = get_provider()
    if not provider.available:
        return {"available": False, "reason": "No AI provider configured"}

    clause = "SELECT * FROM items WHERE is_active = 1"
    if payload.exclude_dirty:
        clause += " AND status NOT IN ('needs_wash','in_wash')"
    wardrobe = []
    for row in db.query(clause):
        item = item_out(row)
        wardrobe.append({
            "id": item["id"], "name": item["name"], "category": item["category"],
            "layer": item["layer"], "colour": item.get("colour_primary"),
            "warmth": item.get("warmth"), "formality": item.get("formality"),
            "waterproof": item.get("water_proof"),
        })
    if not wardrobe:
        return {"available": False, "reason": "Wardrobe is empty"}

    try:
        raw = provider.suggest_outfit({
            "weather_summary": conditions.get("summary"),
            "occasion": payload.occasion,
            "items": wardrobe,
        })
    except Exception as exc:
        return {"available": False, "reason": str(exc)}
    if not raw:
        return {"available": False, "reason": "Provider returned nothing"}

    items = load_items([int(i) for i in raw.get("item_ids", [])])
    scored = recommend.score_outfit(items, conditions, payload.occasion,
                                    recommend.personal_offset()) if items else {}
    return {
        "available": True,
        "name": raw.get("name"),
        "reasoning": raw.get("reasoning"),
        "confidence": raw.get("confidence"),
        "items": items,
        "score": scored.get("score"),
        "warmth": scored.get("warmth"),
    }


@router.get("/suggest/calibration")
def calibration():
    offset = recommend.personal_offset()
    conditions = _conditions(0)
    apparent = conditions.get("apparent_c")
    return {
        "personal_offset": round(offset, 2),
        "base_target": round(recommend.target_warmth(apparent), 1) if apparent is not None else None,
        "adjusted_target": round(recommend.target_warmth(apparent) + offset, 1)
        if apparent is not None else None,
        "feedback_count": (db.query_one("SELECT COUNT(*) AS c FROM comfort_feedback") or {}).get("c", 0),
        "explanation": (
            "Negative means you run warm and get lighter outfits; positive means you feel "
            "the cold and get more layers. It moves as you rate wears."
        ),
    }
