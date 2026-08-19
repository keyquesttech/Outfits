"""Met Office severe weather warnings, from the public RSS feed.

Only surfaced when the Met Office is the selected forecast source, for the
region covering the configured location, and only for warnings in force today.
"""

import math
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

FEED = "https://www.metoffice.gov.uk/public/data/PWSCache/WarningsRSS/Region/{region}"
TIMEOUT = 15
CACHE_TTL = 900  # warnings change slowly; 15 minutes is plenty
UK_TZ = ZoneInfo("Europe/London")

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

# Anchor towns for each warning region. A single centroid per region is too
# crude for shapes like Wales — it puts Cardiff in South West England, because
# Cardiff sits nearer the middle of the West Country than the middle of Wales.
# Matching against the nearest of several real towns fixes that.
REGION_ANCHORS = {
    "se": [(51.51, -0.13), (50.82, -0.14), (50.90, -1.40), (51.75, -1.26),
           (51.28, 1.08), (51.45, -0.97), (52.04, -0.76), (51.82, -0.81),
           (51.06, -1.31), (51.27, -0.79)],
    "sw": [(51.45, -2.59), (50.37, -4.14), (50.72, -3.53), (50.26, -5.05),
           (50.72, -1.88), (51.86, -2.24), (50.07, -5.71), (51.08, -4.06),
           (51.28, -2.20)],
    "ee": [(52.63, 1.30), (52.21, 0.12), (52.06, 1.16), (51.88, -0.42),
           (51.73, 0.48), (52.57, -0.24)],
    "em": [(52.95, -1.15), (52.64, -1.13), (52.92, -1.48), (53.23, -0.54),
           (52.24, -0.90)],
    "wm": [(52.49, -1.89), (52.41, -1.51), (53.00, -2.18), (52.71, -2.75),
           (52.19, -2.22)],
    "nw": [(53.48, -2.24), (53.41, -2.98), (53.76, -2.70), (54.89, -2.94),
           (54.05, -2.80), (54.45, -3.03), (54.15, -4.48)],
    "ne": [(54.98, -1.61), (54.78, -1.58), (54.57, -1.23), (54.91, -1.38),
           (54.97, -2.10), (55.77, -2.01), (55.41, -1.71), (55.13, -2.33)],
    "yh": [(53.80, -1.55), (53.38, -1.47), (53.96, -1.08), (53.75, -0.34),
           (53.80, -1.75)],
    "wl": [(51.48, -3.18), (51.62, -3.94), (52.41, -4.08), (53.23, -4.13),
           (53.05, -3.00), (51.58, -2.99), (52.06, -3.38), (51.88, -4.31),
           (52.75, -3.65), (53.28, -3.83)],
    "ni": [(54.60, -5.93), (54.997, -7.31), (54.35, -6.65), (54.34, -7.63)],
    "dg": [(55.95, -3.19), (55.07, -3.60), (55.62, -2.81), (54.90, -5.02),
           (55.88, -3.52), (55.55, -2.43), (55.94, -2.72)],
    "st": [(55.86, -4.25), (55.85, -4.42), (55.46, -4.63), (56.41, -5.47),
           (55.43, -5.61), (55.95, -4.57)],
    "ta": [(56.12, -3.94), (56.40, -3.44), (56.46, -2.97), (56.07, -3.45),
           (56.34, -2.79), (56.62, -3.87)],
    "gr": [(57.15, -2.09), (57.65, -3.32), (57.51, -1.78), (57.01, -3.40)],
    "he": [(57.48, -4.22), (56.82, -5.11), (57.90, -5.16), (58.21, -6.39),
           (58.59, -3.52), (57.28, -6.19), (58.64, -3.07), (57.59, -7.32),
           (56.95, -7.48)],
    "os": [(58.98, -2.96), (60.15, -1.15), (59.33, -2.60)],
}

# Further than this from any anchor town means the location is not in the UK,
# where Met Office warnings do not apply.
MAX_REGION_KM = 100

LEVELS = {"yellow": 1, "amber": 2, "red": 3}
MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1)}

_cache: dict = {"at": 0.0, "region": None, "data": None}

TITLE_RE = re.compile(
    r"(?P<level>Yellow|Amber|Red)\s+warning\s+of\s+(?P<hazard>.+?)\s+affecting\s+(?P<area>.+)",
    re.IGNORECASE,
)
# "… : Derbyshire, Nottinghamshire valid from 1800 Wed 19 Aug to 0900 Thu 20 Aug"
VALID_RE = re.compile(
    r"valid from\s+(?P<from>\d{4}\s+\w{3}\s+\d{1,2}\s+\w{3})"
    r"\s+to\s+(?P<to>\d{4}\s+\w{3}\s+\d{1,2}\s+\w{3})",
    re.IGNORECASE,
)
COUNTIES_RE = re.compile(r":\s*(?P<counties>[^:]+?)\s+valid from", re.IGNORECASE)


def _haversine_km(a: tuple, b: tuple) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 6371 * 2 * math.asin(math.sqrt(h))


def region_for(lat: float, lon: float) -> dict:
    """Which warning region covers a coordinate, or none if it is outside the UK."""
    best, distance = None, float("inf")
    for code, anchors in REGION_ANCHORS.items():
        d = min(_haversine_km((lat, lon), a) for a in anchors)
        if d < distance:
            best, distance = code, d
    if distance > MAX_REGION_KM:
        return {"code": None, "label": None, "in_uk": False,
                "distance_km": round(distance)}
    return {"code": best, "label": REGIONS[best], "in_uk": True,
            "distance_km": round(distance)}


def _parse_when(text: str, now: datetime) -> datetime | None:
    """Turn '1800 Wed 19 Aug' into a datetime.

    The feed omits the year, so pick whichever year puts the date nearest to
    now — that is what keeps a late-December warning for January correct.
    """
    parts = text.split()
    if len(parts) != 4:
        return None
    hhmm, _weekday, day, month = parts
    if month.title() not in MONTHS or not hhmm.isdigit() or len(hhmm) != 4:
        return None
    try:
        candidates = [
            datetime(year, MONTHS[month.title()], int(day),
                     int(hhmm[:2]), int(hhmm[2:]), tzinfo=UK_TZ)
            for year in (now.year - 1, now.year, now.year + 1)
        ]
    except ValueError:
        return None
    return min(candidates, key=lambda d: abs((d - now).total_seconds()))


def _parse_item(item: ET.Element, now: datetime) -> dict:
    title = (item.findtext("title") or "").strip()
    description = (item.findtext("description") or "").strip()
    link = (item.findtext("link") or "").strip()

    level = hazard = area = None
    match = TITLE_RE.search(title)
    if match:
        level = match.group("level").lower()
        hazard = match.group("hazard").strip().lower()
        area = match.group("area").strip()

    counties = None
    county_match = COUNTIES_RE.search(description)
    if county_match:
        counties = county_match.group("counties").strip()

    starts = ends = None
    period = VALID_RE.search(description)
    if period:
        starts = _parse_when(period.group("from"), now)
        ends = _parse_when(period.group("to"), now)
        # A warning never ends before it starts; that means the year guess for
        # the end fell on the wrong side of a boundary.
        if starts and ends and ends < starts:
            ends = ends.replace(year=ends.year + 1)

    return {
        "title": title,
        "level": level or "yellow",
        "severity": LEVELS.get(level or "yellow", 1),
        "hazard": hazard,
        "area": area,
        "counties": counties,
        "starts_at": starts.isoformat() if starts else None,
        "ends_at": ends.isoformat() if ends else None,
        # 24-hour HH:MM, which is what the feed's "1800" actually means.
        "from_time": starts.strftime("%H:%M") if starts else None,
        "to_time": ends.strftime("%H:%M") if ends else None,
        "from_day": starts.strftime("%a %d %b") if starts else None,
        "to_day": ends.strftime("%a %d %b") if ends else None,
        "description": description,
        "link": link,
        "_starts": starts,
        "_ends": ends,
    }


def _in_force_today(warning: dict, now: datetime) -> bool:
    """True when the warning is active at some point during the rest of today."""
    starts, ends = warning["_starts"], warning["_ends"]
    if not starts or not ends:
        return False
    end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=0)
    return starts <= end_of_day and ends >= now


def _relative(warning: dict, now: datetime) -> str:
    """A short human phrase for when it applies, in 24-hour time."""
    starts, ends = warning["_starts"], warning["_ends"]
    if not starts or not ends:
        return ""
    today = now.date()
    tomorrow = today + timedelta(days=1)

    def day_suffix(dt):
        if dt.date() == today:
            return ""
        if dt.date() == tomorrow:
            return " tomorrow"
        return f" {dt.strftime('%a %d %b')}"

    def label(dt):
        return f"{dt.strftime('%H:%M')}{day_suffix(dt)}"

    if starts <= now:
        return f"until {label(ends)}"
    # Both ends on the same day only needs the day naming once.
    if starts.date() == ends.date():
        return f"{starts.strftime('%H:%M')} to {ends.strftime('%H:%M')}{day_suffix(ends)}"
    return f"{label(starts)} to {label(ends)}"


def fetch(region: str = "uk", force: bool = False, today_only: bool = True) -> dict:
    region = (region or "uk").lower()
    if region not in REGIONS:
        region = "uk"

    now = datetime.now(UK_TZ)
    cache_key = (region, today_only)
    if (not force and _cache["data"] and _cache["region"] == cache_key
            and time.time() - _cache["at"] < CACHE_TTL):
        return _cache["data"]

    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            xml = client.get(FEED.format(region=region)).raise_for_status().text
        channel = ET.fromstring(xml).find("channel")
        items = [_parse_item(i, now)
                 for i in (channel.findall("item") if channel is not None else [])]
    except Exception as exc:
        if _cache["data"]:
            stale = dict(_cache["data"])
            stale["stale"] = True
            return stale
        return {"available": False, "error": str(exc), "region": region,
                "region_label": REGIONS[region], "warnings": [], "count": 0}

    total = len(items)
    if today_only:
        items = [w for w in items if _in_force_today(w, now)]

    for w in items:
        w["when"] = _relative(w, now)
        w["active_now"] = bool(w["_starts"] and w["_starts"] <= now)
        del w["_starts"], w["_ends"]

    items.sort(key=lambda w: (-w["severity"], w["starts_at"] or ""))
    data = {
        "available": True,
        "stale": False,
        "region": region,
        "region_label": REGIONS[region],
        "warnings": items,
        "count": len(items),
        "total_in_region": total,
        "today_only": today_only,
        "highest": items[0]["level"] if items else None,
        "fetched_at": time.time(),
    }
    _cache.update({"at": time.time(), "region": cache_key, "data": data})
    return data
