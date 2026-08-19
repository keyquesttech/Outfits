"""Met Office severe weather warnings, from the public RSS feed.

This feed needs no API key and no account, so warnings are available whichever
forecast provider is selected — including Open-Meteo.
"""

import re
import time
import xml.etree.ElementTree as ET

import httpx

FEED = "https://www.metoffice.gov.uk/public/data/PWSCache/WarningsRSS/Region/{region}"
TIMEOUT = 15
CACHE_TTL = 900  # warnings change slowly; 15 minutes is plenty

REGIONS = {
    "uk": "All of the UK",
    "se": "London & South East England",
    "sw": "South West England",
    "ee": "East of England",
    "em": "East Midlands",
    "wm": "West Midlands",
    "nw": "North West England",
    "ne": "North East England",
    "yh": "Yorkshire & Humber",
    "wl": "Wales",
    "ni": "Northern Ireland",
    "dg": "Dumfries, Galloway, Lothian & Borders",
    "st": "Strathclyde",
    "ta": "Central, Tayside & Fife",
    "gr": "Grampian",
    "he": "Highlands & Eilean Siar",
    "os": "Orkney & Shetland",
}

LEVELS = {"yellow": 1, "amber": 2, "red": 3}

_cache: dict = {"at": 0.0, "region": None, "data": None}

TITLE_RE = re.compile(
    r"(?P<level>Yellow|Amber|Red)\s+warning\s+of\s+(?P<hazard>.+?)\s+affecting\s+(?P<area>.+)",
    re.IGNORECASE,
)
VALID_RE = re.compile(r"valid from\s+(?P<from>.+?)\s+to\s+(?P<to>[^:]+)", re.IGNORECASE)


def _parse_item(item: ET.Element) -> dict:
    title = (item.findtext("title") or "").strip()
    description = (item.findtext("description") or "").strip()
    link = (item.findtext("link") or "").strip()

    level, hazard, area = None, None, None
    match = TITLE_RE.search(title)
    if match:
        level = match.group("level").lower()
        hazard = match.group("hazard").strip().lower()
        area = match.group("area").strip()

    period = VALID_RE.search(description)
    return {
        "title": title,
        "level": level or "yellow",
        "severity": LEVELS.get(level or "yellow", 1),
        "hazard": hazard,
        "area": area,
        "valid_from": period.group("from").strip() if period else None,
        "valid_to": period.group("to").strip() if period else None,
        "description": description,
        "link": link,
    }


def fetch(region: str = "uk", force: bool = False) -> dict:
    region = (region or "uk").lower()
    if region not in REGIONS:
        region = "uk"

    now = time.time()
    if (not force and _cache["data"] and _cache["region"] == region
            and now - _cache["at"] < CACHE_TTL):
        return _cache["data"]

    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            xml = client.get(FEED.format(region=region)).raise_for_status().text
        channel = ET.fromstring(xml).find("channel")
        items = [_parse_item(i) for i in (channel.findall("item") if channel is not None else [])]
    except Exception as exc:
        if _cache["data"]:
            stale = dict(_cache["data"])
            stale["stale"] = True
            return stale
        return {"available": False, "error": str(exc), "region": region,
                "region_label": REGIONS[region], "warnings": []}

    # Nothing to warn about is the common case; keep it cheap to render.
    items.sort(key=lambda w: -w["severity"])
    data = {
        "available": True,
        "stale": False,
        "region": region,
        "region_label": REGIONS[region],
        "warnings": items,
        "count": len(items),
        "highest": items[0]["level"] if items else None,
        "fetched_at": now,
    }
    _cache.update({"at": now, "region": region, "data": data})
    return data
