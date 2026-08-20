"""Gemini provider over the REST API — no SDK, so nothing to keep in step."""

import base64
import json

import httpx

from .base import (
    CARE_PROMPT, CARE_SCHEMA, OUTFIT_SCHEMA, Provider, item_prompt, item_schema,
)

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
TIMEOUT = 90


class GeminiError(RuntimeError):
    pass


class GeminiProvider(Provider):
    name = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash",
                 image_model: str = "gemini-2.5-flash-image"):
        self.api_key = (api_key or "").strip()
        self.model = model or "gemini-2.5-flash"
        self.image_model = image_model or "gemini-2.5-flash-image"
        self.available = bool(self.api_key)

    def _post(self, model: str, body: dict) -> dict:
        if not self.available:
            raise GeminiError("No Gemini API key configured")
        url = ENDPOINT.format(model=model)
        headers = {"x-goog-api-key": self.api_key, "Content-Type": "application/json"}
        with httpx.Client(timeout=TIMEOUT) as client:
            resp = client.post(url, headers=headers, json=body)
        if resp.status_code >= 400:
            raise GeminiError(f"Gemini HTTP {resp.status_code}: {resp.text[:300]}")
        return resp.json()

    @staticmethod
    def _parts(payload: dict) -> list:
        for cand in payload.get("candidates", []) or []:
            parts = (cand.get("content") or {}).get("parts") or []
            if parts:
                return parts
        return []

    def _structured(self, prompt: str, schema: dict, image: bytes | None,
                    mime: str = "image/jpeg") -> dict:
        parts: list = [{"text": prompt}]
        if image is not None:
            parts.append({
                "inline_data": {"mime_type": mime, "data": base64.b64encode(image).decode()}
            })
        payload = self._post(self.model, {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": schema,
                "temperature": 0.2,
            },
        })
        text = "".join(p.get("text", "") for p in self._parts(payload)).strip()
        if not text:
            raise GeminiError("Gemini returned no content")
        try:
            return json.loads(text)
        except ValueError as exc:
            raise GeminiError(f"Gemini returned non-JSON: {text[:200]}") from exc

    def analyse_item(self, image: bytes, mime: str = "image/jpeg") -> dict | None:
        return self._structured(item_prompt(), item_schema(), image, mime)

    def read_care_label(self, image: bytes, mime: str = "image/jpeg") -> dict | None:
        return self._structured(CARE_PROMPT, CARE_SCHEMA, image, mime)

    def remove_background(self, image: bytes, mime: str = "image/jpeg") -> bytes | None:
        """Best effort. Returns None if the image model is unavailable."""
        prompt = ("Remove the background from this photo of a clothing item completely. "
                  "Keep the garment exactly as-is, centred, with a fully transparent "
                  "background. Do not add shadows, text, or any other object.")
        try:
            payload = self._post(self.image_model, {
                "contents": [{"role": "user", "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": mime,
                                     "data": base64.b64encode(image).decode()}},
                ]}],
            })
        except GeminiError:
            return None
        for part in self._parts(payload):
            blob = part.get("inline_data") or part.get("inlineData")
            if blob and blob.get("data"):
                return base64.b64decode(blob["data"])
        return None

    def suggest_outfit(self, context: dict) -> dict | None:
        prompt = (
            "You are a personal stylist choosing one outfit from a real wardrobe.\n"
            f"Weather: {context.get('weather_summary')}\n"
            f"Occasion: {context.get('occasion') or 'everyday'}\n"
            f"Notes: {context.get('notes') or 'none'}\n\n"
            "Pick items from this list only, using their numeric ids. Choose one "
            "coherent outfit: a top, a bottom (or a dress), footwear, plus outer "
            "layers if the weather needs them, and at most two accessories.\n"
            "Every item's warmth is 1-10 and formality 1-5.\n\n"
            f"Wardrobe:\n{json.dumps(context.get('items', []), separators=(',', ':'))}\n\n"
            "Explain the choice in two sentences, referring to weather and colour."
        )
        return self._structured(prompt, OUTFIT_SCHEMA, None)

    def check(self) -> dict:
        try:
            payload = self._post(self.model, {
                "contents": [{"role": "user", "parts": [{"text": "Reply with the word OK."}]}],
                "generationConfig": {"temperature": 0},
            })
            text = "".join(p.get("text", "") for p in self._parts(payload)).strip()
            return {"ok": True, "model": self.model, "reply": text[:80]}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
