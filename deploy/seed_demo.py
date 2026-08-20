#!/usr/bin/env python3
"""Fill a wardrobe with realistic sample data so the app can be explored before
you photograph anything real.

    .venv/bin/python deploy/seed_demo.py --url http://localhost

Generates garment images, saved outfits, and six weeks of
wear history with comfort ratings so the analytics and calibration panels have
something to show. Use --wipe to clear an existing demo first.
"""

import argparse
import io
import random
import sys
from datetime import date, timedelta

import httpx
from PIL import Image, ImageDraw, ImageFilter

BACKDROP = (240, 238, 234)

# name, category, rgb, shape, warmth, formality, seasons, extras
WARDROBE = [
    ("White oxford shirt",     "shirt",     (248, 248, 244), "shirt",  3, 4, ["spring", "autumn"], {}),
    ("Pale blue oxford shirt", "shirt",     (176, 202, 230), "shirt",  3, 4, ["spring", "summer"], {}),
    ("Grey marl t-shirt",      "top",       (150, 148, 145), "tee",    2, 2, ["summer"], {}),
    ("White t-shirt",          "top",       (246, 246, 242), "tee",    2, 2, ["summer"], {}),
    ("Navy merino jumper",     "knitwear",  (32, 46, 84),    "jumper", 6, 3, ["autumn", "winter"], {}),
    ("Oatmeal lambswool crew", "knitwear",  (214, 196, 166), "jumper", 6, 3, ["autumn", "winter"], {}),
    ("Charcoal wool coat",     "outerwear", (56, 56, 60),    "coat",   9, 4, ["winter"],
     {"wind_proof": True}),
    ("Olive field jacket",     "outerwear", (104, 110, 72),  "coat",   6, 2, ["autumn", "spring"],
     {"water_proof": True, "wind_proof": True}),
    ("Indigo selvedge jeans",  "bottom",    (52, 66, 96),    "trouser", 4, 2, ["autumn", "winter", "spring"], {}),
    ("Black slim jeans",       "bottom",    (38, 38, 40),    "trouser", 4, 2, ["autumn", "winter"], {}),
    ("Stone chinos",           "bottom",    (198, 182, 152), "trouser", 3, 3, ["spring", "summer"], {}),
    ("Charcoal wool trousers", "bottom",    (62, 62, 68),    "trouser", 5, 5, ["autumn", "winter"], {}),
    ("Brown leather boots",    "footwear",  (108, 72, 44),   "boot",   4, 3, ["autumn", "winter"], {}),
    ("White leather trainers", "footwear",  (240, 238, 232), "shoe",   2, 2, ["spring", "summer"], {}),
    ("Black derby shoes",      "footwear",  (30, 30, 32),    "shoe",   3, 5, ["autumn", "winter"], {}),
    ("Burgundy lambswool scarf", "scarf",   (108, 34, 52),   "scarf",  4, 3, ["winter"], {}),
    ("Charcoal beanie",        "headwear",  (58, 58, 62),    "beanie", 3, 1, ["winter"], {}),
    ("Tan leather belt",       "belt",      (156, 106, 62),  "belt",   0, 3, [], {}),
    ("Steel dive watch",       "watch",     (188, 190, 194), "watch",  0, 3, [], {}),
    ("Gold signet ring",       "jewellery", (206, 170, 82),  "ring",   0, 3, [], {}),
    ("Black wool socks",       "sock",      (36, 36, 38),    "sock",   2, 2, ["autumn", "winter"], {}),
    ("Grey cotton socks",      "sock",      (140, 140, 142), "sock",   1, 2, ["spring", "summer"], {}),
]

# A few fits so the demo exercises the control.
FITS = {
    "Indigo selvedge jeans": "regular",
    "Black slim jeans": "skinny",
    "Stone chinos": "loose",
    "Charcoal wool trousers": "regular",
    "White oxford shirt": "slim",
    "Pale blue oxford shirt": "regular",
    "Grey marl t-shirt": "regular",
    "White t-shirt": "oversized",
}

OUTFIT_PLANS = [
    ("Office standard", "work", ["White oxford shirt", "Charcoal wool trousers", "Black derby shoes", "Steel dive watch"]),
    ("Weekend uniform", "casual", ["Grey marl t-shirt", "Indigo selvedge jeans", "White leather trainers"]),
    ("Cold commute", "work", ["Pale blue oxford shirt", "Navy merino jumper", "Charcoal wool coat",
                              "Charcoal wool trousers", "Black derby shoes", "Burgundy lambswool scarf"]),
    ("Pub Sunday", "casual", ["Oatmeal lambswool crew", "Black slim jeans", "Brown leather boots"]),
    ("Warm evening out", "date", ["White t-shirt", "Stone chinos", "White leather trainers", "Gold signet ring"]),
]


def shape_image(rgb, shape):
    """A recognisable garment silhouette — enough for colour extraction to bite on.

    Every shape carries a darker edge. Without it a white shirt on a pale
    backdrop is invisible in a thumbnail, exactly as it would be in a real photo
    shot against a white wall.
    """
    W, H = 720, 960
    img = Image.new("RGB", (W, H), BACKDROP)
    d = ImageDraw.Draw(img)
    dark = tuple(max(0, c - 28) for c in rgb)
    edge = tuple(max(0, int(c * 0.62)) for c in rgb)
    E = {"outline": edge, "width": 3}

    if shape in ("shirt", "tee"):
        sleeve = 250 if shape == "shirt" else 210
        d.polygon([(230, 250), (490, 250), (600, 330), (545, sleeve + 170), (490, 400),
                   (490, 760), (230, 760), (230, 400), (175, sleeve + 170), (120, 330)],
                  fill=rgb, **E)
        d.ellipse([300, 225, 420, 290], fill=BACKDROP, **E)
        if shape == "shirt":
            d.line([(360, 270), (360, 755)], fill=dark, width=4)
    elif shape == "jumper":
        d.polygon([(215, 265), (505, 265), (615, 355), (585, 620), (505, 560),
                   (505, 790), (215, 790), (215, 560), (135, 620), (105, 355)], fill=rgb, **E)
        d.ellipse([295, 235, 425, 305], fill=BACKDROP, **E)
        d.rectangle([215, 760, 505, 790], fill=dark)
    elif shape == "coat":
        d.polygon([(200, 250), (520, 250), (630, 350), (600, 700), (540, 640),
                   (540, 870), (180, 870), (180, 640), (120, 700), (90, 350)], fill=rgb, **E)
        d.ellipse([290, 220, 430, 300], fill=BACKDROP, **E)
        d.line([(360, 280), (360, 865)], fill=dark, width=5)
        for y in (400, 470, 540):
            d.ellipse([335, y, 355, y + 20], fill=dark)
    elif shape == "trouser":
        d.polygon([(230, 210), (490, 210), (500, 300), (480, 860), (390, 860),
                   (360, 430), (330, 860), (240, 860), (220, 300)], fill=rgb, **E)
        d.rectangle([230, 210, 490, 250], fill=dark)
    elif shape == "boot":
        d.polygon([(250, 330), (430, 330), (445, 620), (520, 640), (525, 720),
                   (240, 720), (235, 620)], fill=rgb, **E)
        d.rectangle([235, 700, 525, 730], fill=dark)
    elif shape == "shoe":
        d.polygon([(215, 500), (400, 490), (500, 560), (530, 640), (215, 645)], fill=rgb, **E)
        d.rectangle([210, 630, 532, 665], fill=dark)
    elif shape == "scarf":
        d.polygon([(280, 190), (440, 190), (430, 700), (470, 830), (390, 840),
                   (360, 720), (330, 840), (250, 830), (290, 700)], fill=rgb, **E)
    elif shape == "beanie":
        d.pieslice([220, 300, 500, 620], start=180, end=360, fill=rgb, **E)
        d.rectangle([220, 455, 500, 545], fill=dark)
    elif shape == "belt":
        d.rounded_rectangle([120, 430, 600, 500], radius=18, fill=rgb, **E)
        d.rectangle([560, 405, 620, 525], outline=tuple(min(255, c + 40) for c in rgb), width=14)
    elif shape == "watch":
        strap = tuple(max(0, c - 60) for c in rgb)
        d.rounded_rectangle([320, 250, 400, 460], radius=22, fill=strap, **E)
        d.rounded_rectangle([320, 520, 400, 730], radius=22, fill=strap, **E)
        d.ellipse([275, 420, 445, 590], fill=rgb, **E)
        d.ellipse([300, 445, 420, 565], fill=(28, 32, 40))
    elif shape == "ring":
        d.ellipse([270, 330, 450, 640], outline=rgb, width=42)
        d.ellipse([310, 300, 410, 400], fill=rgb, **E)
    elif shape == "sock":
        d.polygon([(290, 220), (410, 220), (415, 560), (520, 590), (525, 690),
                   (300, 690), (285, 560)], fill=rgb, **E)
        d.rectangle([290, 220, 410, 270], fill=dark)

    return img.filter(ImageFilter.SMOOTH)


def to_jpeg(img):
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=92)
    return buf.getvalue()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost", help="Base URL of the running app")
    ap.add_argument("--wipe", action="store_true", help="Delete every existing item first")
    ap.add_argument("--weeks", type=int, default=6, help="Weeks of wear history to invent")
    args = ap.parse_args()

    random.seed(7)
    c = httpx.Client(base_url=args.url, timeout=60)

    try:
        c.get("/api/health").raise_for_status()
    except Exception as exc:
        print(f"Cannot reach {args.url}: {exc}", file=sys.stderr)
        return 1

    if args.wipe:
        existing = c.get("/api/items", params={"include_inactive": True}).json()["items"]
        for item in existing:
            c.delete(f"/api/items/{item['id']}?hard=true")
        for o in c.get("/api/outfits").json()["outfits"]:
            c.delete(f"/api/outfits/{o['id']}")
        print(f"Wiped {len(existing)} items")

    print("Creating wardrobe…")
    ids = {}
    for name, cat, rgb, shape, warmth, formality, seasons, extras in WARDROBE:
        blob = to_jpeg(shape_image(rgb, shape))
        r = c.post("/api/items/upload",
                   files={"file": (f"{name}.jpg", blob, "image/jpeg")},
                   data={"name": name, "category": cat, "analyse": "false"})
        r.raise_for_status()
        item = r.json()
        ids[name] = item["id"]
        c.patch(f"/api/items/{item['id']}", json={
            "warmth": warmth, "formality": formality, "seasons": seasons,
            **extras,
        })
        fit = FITS.get(name)
        if fit:
            c.patch(f"/api/items/{item['id']}", json={"fit": fit})
        print(f"  {name}  ({item['colour_primary']})")

    print("Saving outfits…")
    outfit_ids = {}
    for name, occasion, members in OUTFIT_PLANS:
        item_ids = [ids[m] for m in members if m in ids]
        r = c.post("/api/outfits", json={"name": name, "occasion": occasion, "item_ids": item_ids})
        outfit_ids[name] = r.json()["id"]
        print(f"  {name}")

    # Real past weather, so the comfort calibration learns from honest numbers
    # rather than today's temperature stamped on every historical day.
    print("Fetching past weather…")
    past = {}
    try:
        r = httpx.get("https://api.open-meteo.com/v1/forecast", timeout=20, params={
            "latitude": 51.5072, "longitude": -0.1276, "timezone": "Europe/London",
            "past_days": min(92, args.weeks * 7 + 1), "forecast_days": 1,
            "daily": "temperature_2m_max,temperature_2m_min,"
                     "apparent_temperature_max,apparent_temperature_min",
        })
        d = r.raise_for_status().json()["daily"]
        for i, day in enumerate(d["time"]):
            past[day] = (
                (d["temperature_2m_max"][i] + d["temperature_2m_min"][i]) / 2,
                (d["apparent_temperature_max"][i] + d["apparent_temperature_min"][i]) / 2,
            )
        print(f"  got {len(past)} days")
    except Exception as exc:
        print(f"  unavailable ({exc}); history will have no weather attached")

    print(f"Inventing {args.weeks} weeks of history…")
    today = date.today()
    logged = 0
    for days_ago in range(args.weeks * 7, 0, -1):
        day = today - timedelta(days=days_ago)
        if random.random() < 0.22:      # rest days
            continue
        weekday = day.weekday()
        if weekday < 5:
            plan = random.choice(["Office standard", "Cold commute", "Office standard"])
            occasion = "work"
        else:
            plan = random.choice(["Weekend uniform", "Pub Sunday", "Warm evening out"])
            occasion = "casual"
        members = [ids[m] for m in dict(
            (n, ms) for n, _, ms in OUTFIT_PLANS)[plan] if m in ids]
        socks = ids["Black wool socks"] if weekday < 5 else ids["Grey cotton socks"]
        payload = {
            "item_ids": members + [socks],
            "outfit_id": outfit_ids[plan],
            "occasion": occasion,
            "worn_on": day.isoformat(),
            "use_weather": False,
            "rating": random.choice([3, 4, 4, 5, 5]),
        }
        weather_that_day = past.get(day.isoformat())
        if weather_that_day:
            payload["temp_c"], payload["apparent_c"] = weather_that_day
            # Comfort feedback needs a temperature to be worth anything, so it is
            # only offered on days we know the weather for.
            if random.random() < 0.45:
                payload["comfort_rating"] = random.choice([1, 1, 0, -1])
        c.post("/api/wear", json=payload)
        logged += 1

    summary = c.get("/api/analytics/summary").json()
    print(f"\nDone. {summary['active_items']} items, {logged} days logged, "
          f"{summary['total_wears']} wears.")
    print(f"Open {args.url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
