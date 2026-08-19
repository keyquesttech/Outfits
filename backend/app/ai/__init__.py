from .. import db
from .base import Provider
from .gemini import GeminiProvider


def get_provider() -> Provider:
    """Resolve the configured provider. Always returns something callable."""
    choice = (db.get_setting("ai_provider", "none") or "none").lower()
    if choice == "gemini":
        key = db.get_setting("gemini_api_key", "")
        if key:
            return GeminiProvider(
                key,
                db.get_setting("gemini_model", "gemini-2.5-flash"),
                db.get_setting("gemini_image_model", "gemini-2.5-flash-image"),
            )
    return Provider()


__all__ = ["get_provider", "Provider", "GeminiProvider"]
