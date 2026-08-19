import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("OUTFITS_DATA", BASE_DIR / "data"))
PHOTO_DIR = DATA_DIR / "photos"
ORIG_DIR = PHOTO_DIR / "orig"
THUMB_DIR = PHOTO_DIR / "thumb"
CUTOUT_DIR = PHOTO_DIR / "cutout"
DB_PATH = Path(os.environ.get("OUTFITS_DB", DATA_DIR / "outfits.db"))
STATIC_DIR = BASE_DIR / "frontend" / "dist"

HOST = os.environ.get("OUTFITS_HOST", "0.0.0.0")
PORT = int(os.environ.get("OUTFITS_PORT", "80"))

# London. Overridable in settings at runtime.
DEFAULT_LAT = 51.5072
DEFAULT_LON = -0.1276
DEFAULT_TZ = "Europe/London"

MAX_IMAGE_PX = 1600
THUMB_PX = 400
UPLOAD_MAX_BYTES = 25 * 1024 * 1024

DEFAULT_SETTINGS = {
    "ai_provider": "none",          # none | gemini
    "gemini_api_key": "",
    "gemini_model": "gemini-2.5-flash",
    "latitude": str(DEFAULT_LAT),
    "longitude": str(DEFAULT_LON),
    "timezone": DEFAULT_TZ,
    "location_name": "London, UK",
    "units": "metric",
    "warmth_offset": "0",           # learned personal calibration, in °C
    "weather_provider": "open-meteo",   # open-meteo | metoffice
    "metoffice_api_key": "",
    "metoffice_optimize": "1",          # 1 = long cache, single request per refresh
    "metoffice_usage_month": "",
    "metoffice_usage_calls": "0",
    "warnings_enabled": "1",
    "warnings_region": "uk",
}


def ensure_dirs() -> None:
    for d in (DATA_DIR, PHOTO_DIR, ORIG_DIR, THUMB_DIR, CUTOUT_DIR):
        d.mkdir(parents=True, exist_ok=True)
