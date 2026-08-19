"""Approximate location from the public IP address.

Browsers only expose GPS on secure origins, and this app is served over plain
HTTP on the LAN, so `navigator.geolocation` is unavailable to it. An IP lookup
needs no permission and no HTTPS, and resolves to roughly the right town —
which is all a weather forecast needs.

The lookup runs from the Pi, so it finds where the Pi's network is. For a
wardrobe that lives at home, that is the right answer even when you are out.
"""

import time

import httpx

TIMEOUT = 10
CACHE_TTL = 3600

# Both are free, keyless and HTTPS. Tried in order.
SERVICES = [
    {
        "name": "ipapi.co",
        "url": "https://ipapi.co/json/",
        "map": lambda d: {
            "latitude": d.get("latitude"),
            "longitude": d.get("longitude"),
            "city": d.get("city"),
            "region": d.get("region"),
            "country": d.get("country_name"),
            "timezone": d.get("timezone"),
            "ip": d.get("ip"),
        },
    },
    {
        "name": "ipwho.is",
        "url": "https://ipwho.is/",
        "map": lambda d: {
            "latitude": d.get("latitude"),
            "longitude": d.get("longitude"),
            "city": d.get("city"),
            "region": d.get("region"),
            "country": d.get("country"),
            "timezone": (d.get("timezone") or {}).get("id"),
            "ip": d.get("ip"),
        },
    },
]

_cache: dict = {"at": 0.0, "data": None}


def locate(force: bool = False) -> dict:
    now = time.time()
    if not force and _cache["data"] and now - _cache["at"] < CACHE_TTL:
        return _cache["data"]

    errors = []
    for service in SERVICES:
        try:
            with httpx.Client(timeout=TIMEOUT) as client:
                raw = client.get(service["url"]).raise_for_status().json()
            found = service["map"](raw)
            if found.get("latitude") is None or found.get("longitude") is None:
                errors.append(f"{service['name']}: no coordinates in response")
                continue
            parts = [found.get("city"), found.get("region"), found.get("country")]
            data = {
                "available": True,
                "source": service["name"],
                "accuracy": "network",
                "latitude": round(float(found["latitude"]), 4),
                "longitude": round(float(found["longitude"]), 4),
                "timezone": found.get("timezone"),
                "label": ", ".join(p for p in parts if p),
                "city": found.get("city"),
            }
            _cache.update({"at": now, "data": data})
            return data
        except Exception as exc:
            errors.append(f"{service['name']}: {exc}")

    return {"available": False, "errors": errors,
            "message": "Could not work out the location from the network."}
