from fastapi import APIRouter, HTTPException

from .. import db, jobs, weather
from ..ai import get_provider
from ..ai.gemini import GeminiProvider
from ..models import SettingsIn

router = APIRouter(prefix="/api", tags=["settings"])

SECRET_KEYS = {"gemini_api_key", "metoffice_api_key"}
ALLOWED = {
    "ai_provider", "gemini_api_key", "gemini_model", "gemini_image_model",
    "latitude", "longitude", "timezone", "location_name", "units", "warmth_offset",
    "weather_provider", "metoffice_api_key", "metoffice_optimize",
    "warnings_enabled", "style_notes",
}


def _redacted() -> dict:
    values = db.all_settings()
    out = {}
    for key, value in values.items():
        if key in SECRET_KEYS:
            out[key] = ""
            out[f"{key}_set"] = bool(value)
        else:
            out[key] = value
    return out


@router.get("/settings")
def get_settings():
    provider = get_provider()
    return {
        "settings": _redacted(),
        "ai": {"provider": provider.name, "available": provider.available},
        "providers": ["none", "gemini"],
        "weather_providers": weather.provider_info(),
        "weather_usage": weather.usage(),
        # The warning region follows the configured location rather than being
        # picked by hand, so the UI shows what was derived.
        "warning_region": weather.warnings.region_for(
            float(db.get_setting("latitude", "51.5072") or 51.5072),
            float(db.get_setting("longitude", "-0.1276") or -0.1276),
        ),
    }


@router.put("/settings")
def put_settings(payload: SettingsIn):
    unknown = set(payload.values) - ALLOWED
    if unknown:
        raise HTTPException(400, f"Unknown settings: {', '.join(sorted(unknown))}")
    for key, value in payload.values.items():
        # An empty API key means "leave it alone", so the UI never has to echo it back.
        if key in SECRET_KEYS and value == "":
            continue
        db.set_setting(key, value)
    # Anything that changes what would be fetched invalidates the cached forecast.
    if {"latitude", "longitude", "timezone", "weather_provider",
            "metoffice_api_key", "metoffice_optimize"} & set(payload.values):
        weather.fetch(force=True)
    return get_settings()


@router.post("/settings/ai/test")
def test_ai():
    provider = get_provider()
    if not provider.available:
        return {"ok": False, "error": "No AI provider configured",
                "hint": "Choose Gemini and paste an API key, or leave AI off — "
                        "everything except auto-tagging works without it."}
    if isinstance(provider, GeminiProvider):
        return provider.check()
    return {"ok": True, "provider": provider.name}


@router.get("/jobs")
def job_status():
    return jobs.status()


@router.post("/jobs/{job_id}/retry")
def retry_job(job_id: int):
    row = db.query_one("SELECT * FROM jobs WHERE id = ?", (job_id,))
    if not row:
        raise HTTPException(404, "Job not found")
    db.execute("UPDATE jobs SET status = 'queued', error = NULL, result = NULL, "
               "updated_at = datetime('now') WHERE id = ?", (job_id,))
    return {"job_id": job_id, "status": "queued"}


@router.get("/health")
def health():
    counts = db.query_one("SELECT COUNT(*) AS items FROM items") or {}
    provider = get_provider()
    return {
        "ok": True,
        "items": counts.get("items", 0),
        "ai_provider": provider.name,
        "ai_available": provider.available,
        "worker": jobs.status()["worker_alive"],
    }
