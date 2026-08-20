# Outfits

A self-hosted wardrobe manager running on a Raspberry Pi. Photograph what you own,
build outfits, get suggestions scored against the London weather, and keep track of
what needs washing.

**Live at [http://outfits.local/](http://outfits.local/)** on the local network.

---

## What it does

**Photo wardrobe.** Upload or photograph an item and it is catalogued. Colours are read
from the photo automatically — plain image processing, not AI, so it works with no API key
and no model. Pixels are weighted towards the middle of the frame, since a garment is
nearly always centred and the edges are hanger, floor and wall; the backdrop is read from a
ring around the whole border; and each colour cluster knows how much of itself is pressed
against that border, which is what separates a garment from its own shadow. The swatches
are only a **starting point**: they fill the primary and secondary colour fields, and those
fields are what outfit matching uses.

**Colours, named the way you would name them.** Naming happens in CIE Lab, and the
lightness bands are set from photographed garments rather than from a colour chart. Black
fabric photographs at L\* 10-20, not 0, so nearest-neighbour against a textbook palette
called every black t-shirt "charcoal"; white fabric lands at L\* 84-88, not 100, so every
white shirt came back "silver". Hue only gets a vote once there is enough chroma to trust
it — camera white balance alone moves a neutral grey further than a washed-out army green
sits from grey.

Where the pixels genuinely cannot decide, the app does not guess harder. A white tee and a
pale grey marl photograph two Lab units apart, and a desaturated olive measures as a grey,
so each swatch carries its **runners-up**, offered after "or" in the form and one tap away.

Colour fields stay free text, but everything typed into them resolves through one table:
"Gray", "Dark Red", "off-white", "army green", "#1b1b1d" and "N/A" all land where they
should. That table is what the laundry piles, the outfit matcher, the colour filter and the
analytics chart read, so a spelling can no longer fall silently through all four. A word
the app does not know is kept exactly as typed and flagged in the form, never overwritten.

**Settings → Colours** re-reads every photo with the current engine — filling in only what
is blank or unrecognised, or overwriting the lot, whichever you ask for.

**Rotate and crop, before or after uploading.** Every photo gets an optional editor:
rotate in 90° steps, drag a crop box, or lock it to 3:4, 1:1 or 4:3. It runs in the
browser, so what you see is exactly what is stored. "Edit photo" on an item reopens the
picture already saved, so a crooked shot can be straightened without taking it again.

**Tag by hand or let AI do it.** When adding items you choose: *Tag them myself* opens a
form for each photo right after uploading, stepping through them one at a time with the
detected colours offered as one-tap choices. *Let AI tag them* fills in category,
material, pattern, warmth and formality for you to confirm, and needs a Gemini key. Every
field stays editable afterwards either way.

**Categories are yours.** The built-in set is a starting point, not a fixture. Add your own
in Settings → Categories, rename them, or remove the ones you do not wear. The wardrobe
filter shows only categories you actually own something in, with a count, so a rail of
nineteen chips is however many you really use.

Adding one asks two questions: what it is called, and which **layer** it occupies — base,
bottom, top, mid, outer, footwear, accessory or jewellery. The layer is the part that
matters, because it decides which slot the garment fills and the outfit builder only puts
one thing in each. Warmth, formality and wears-before-washing are taken from the layer
unless you set them; all three stay editable per garment either way.

Removing a category that still holds garments asks where they should go first. Deleting it
outright would leave them naming something nothing recognises — no layer, so no outfits,
and no wash threshold — so either the items move, or the delete is refused.

An item can sit in **more than one category** — joggers filed as both Bottom and Pyjamas
turn up under either filter, and count towards both. The main category still decides the
layer, the wash default and how the outfit builder uses it, since a garment can only fill
one slot in an outfit at a time; the extras are for finding things.

Trousers, shirts, tops, knitwear and outerwear also carry a **fit** — skinny, regular,
loose, oversized and so on, chosen per category. Bottoms carry a **belt** toggle: turn it
off for elasticated or drawstring trousers and the builder will not put a belt with them.

Text fields capitalise each word as you type and offer what you have entered before, so a
brand only has to be typed once. Tagging an item runs straight into its washing and care
details, since that is what sorts it into the right laundry load later.

Warmth is **Cold / Neutral / Hot**, formality is **Casual / Informal / Formal**, and
damage is **None / Mild / Bad** — three buttons each rather than a slider. Damage is about
the garment's condition, separate from whether it needs washing: a shirt can be clean and
still have a hole in it. Anything not "None" shows as a badge on the item. Underneath, warmth is still a 0-10 number because the
recommender adds it up and compares the total against a temperature, and the three buttons
map relative to the category: "hot" for a t-shirt is not the same number as "hot" for an
overcoat.

**Weather-aware suggestions.** Outfits are scored on total insulation against the
feels-like temperature, plus rain, wind, occasion and colour harmony. Every suggestion
shows its reasoning, so a bad suggestion tells you which dial to turn.

**Two forecast sources.** Open-Meteo (free, keyless, global) or the Met Office DataHub
Site Specific API for the UK. Met Office needs a free API key.

The forecast refreshes **once every five hours** — about five calls a day, roughly 144 a
month with **Optimise for the free plan** on, which uses a single three-hourly request
instead of two. Pressing refresh on the Today page fetches immediately regardless. Usage
is counted and shown in Settings.

**Severe weather warnings.** Met Office warnings shown on the Today page, deliberately
narrow: only while the Met Office is the selected forecast source, only for the region
covering your location (derived from your coordinates, not picked from a list), and only
for warnings in force today. Times are 24-hour, so "until 09:00 tomorrow" rather than the
feed's raw "0900 Thu 20 Aug".

**Set your location** by searching for a place name, from your device's GPS, or by typing
coordinates.

**It learns how you feel the cold.** Rate a wear "too hot", "just right" or "too cold"
and your personal warmth offset shifts. The app converges on how *you* experience 12 °C
rather than assuming an average body.

**Washing that understands garments.** Each item has its own wear threshold — socks
after one wear, a shirt after two, a coat after twenty-five. Once things are dirty the
laundry view groups them into loads that can actually go in the machine together, split
by temperature and colour, with wool and delicates kept separate. Care instructions can
be typed in or read from a photograph of the care label.

**Pyjamas** are a category of their own, and like a dress they count as covering top and
bottom, so the builder never pairs them with trousers. They start at lounge formality, so
they do not turn up in a suggestion for work.

**Jewellery and accessories** are first-class: they flow through outfits and analytics
like everything else, they never enter the wash pile, and metal tones are treated as
metal rather than as a clashing colour.

**Wear history.** Every item lists when it was worn, for what, how the weather felt and
how you rated it. Any entry can be deleted, which puts the wear counters back — including
progress towards the next wash.

**Analytics.** Most and least worn, things untouched for 90 days, colour distribution,
repeated pairings, laundry history, and gaps limiting your suggestions. The wardrobe can
also be filtered by colour, offering only the colours you actually own.

**AI is entirely optional.** Choose "No AI" and everything above still works except
automatic tagging and care-label reading.

---

## How it coexists with FlatBrain

FlatBrain's Node process binds `*:80` — the wildcard address on every interface. Nothing
else can bind port 80 in the host's network stack, and a specific IP fails with
`EADDRINUSE` even with `SO_REUSEADDR` (measured, not assumed).

So Outfits runs in **its own Linux network namespace**, with its own MAC address and its
own LAN IP. Inside that namespace port 80 is a completely separate port, so a conflict is
not merely avoided — it is impossible.

```
                    eth0 (physical)
                          |
        +-----------------+------------------+
        |                                    |
   host stack                         macvlan "outfits0"
   192.168.86.28                      192.168.86.251
   flatbrain.local                    outfits.local
   node :80   (UNTOUCHED)             uvicorn :80
                                      [netns: outfits]
```

FlatBrain's code, port, systemd unit, avahi record and hostname are all unmodified, as
are `/etc/resolv.conf` and `avahi-daemon.conf`. Installing Outfits adds three systemd
units and one mDNS record; it changes nothing that already existed.

**The Pi itself cannot reach `192.168.86.251`** — macvlan deliberately isolates a child
interface from its parent. Phones and laptops on the network reach it normally. From the
Pi, use:

```bash
sudo ip netns exec outfits curl http://localhost/api/health
```

---

## Stack

| Layer | Choice | Why |
| --- | --- | --- |
| Backend | FastAPI + uvicorn | One process, ~150 MB idle |
| Database | SQLite (WAL) | One file; backup is a file copy |
| Images | Pillow | EXIF rotation, thumbnails, colour extraction |
| Frontend | React + Vite + Tailwind | Built to static files, served by FastAPI |
| Jobs | SQLite table + one thread | No Redis for a single user |
| Weather | Open-Meteo | Free, keyless |
| AI | Gemini REST (optional) | No SDK to keep in step |

No Postgres, no Redis, no Docker. The built frontend is 93 KB gzipped.

---

## Install

```bash
sudo bash deploy/install.sh
```

Installs three units and verifies the result, including that FlatBrain is untouched:

- `outfits-netns.service` — creates the namespace and macvlan
- `outfits-mdns.service` — publishes `outfits.local`
- `outfits.service` — the app

Configuration lives in `/etc/default/outfits`. Change `OUTFITS_IP` there if
`192.168.86.251` is not free on your network — it must sit outside the router's DHCP
pool, or be reserved for the macvlan's MAC.

To remove everything (your data is left alone):

```bash
sudo bash deploy/uninstall.sh
```

---

## Try it with sample data

```bash
sudo ip netns exec outfits /home/pi/Outfits/.venv/bin/python deploy/seed_demo.py --url http://localhost
```

Creates 22 items with generated photos, care instructions, five outfits, and six weeks of
wear history using real past weather so the calibration panel has honest data. Add
`--wipe` to clear it out again.

---

## Development

```bash
cd frontend && npm run dev
```

Runs Vite on port 5173, proxying the API to `127.0.0.1:8099`. Start a backend there with:

```bash
OUTFITS_DATA=/tmp/outfits-dev PYTHONPATH=backend .venv/bin/uvicorn app.main:app --port 8099
```

After changing the frontend, rebuild and restart:

```bash
cd frontend && npm run build && sudo systemctl restart outfits
```

API documentation is at `/docs`.

The colour engine has its own checks, measured off real wardrobe photos rather than
invented. They run under pytest, and on their own where pytest is not installed:

```bash
PYTHONPATH=backend .venv/bin/python backend/tests/test_colours.py
PYTHONPATH=backend .venv/bin/python backend/tests/test_categories.py
```

---

## Backups

```bash
deploy/backup.sh
```

Uses SQLite's own backup command, so it is safe to run while the app is writing. Keeps the
ten most recent archives. Everything that matters is `data/outfits.db` and `data/photos/`.

---

## Setting up AI

Optional. Get a key from [aistudio.google.com/apikey](https://aistudio.google.com/apikey),
then in Settings choose Gemini, paste the key, and press "Test connection". The key is
stored in the local database and never sent back to the browser.

Turning AI off at any point leaves everything else working.

---

## Setting up the Met Office forecast

Also optional — Open-Meteo is the default and needs nothing.

1. Create a free account at [datahub.metoffice.gov.uk](https://datahub.metoffice.gov.uk/)
   and subscribe to **Site Specific** (Global Spot).
2. In Settings → Weather, pick Met Office, paste the key, and press "Test connection".
   The test reports the temperature it read back and names any fields it could not find.
3. Leave **Optimise for the free plan** ticked unless you have allowance to spare.

Endpoints used, verified against the live service:

```
GET https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point/{hourly,three-hourly,daily}
    ?latitude=..&longitude=..
Header: apikey: <your key>
```

Optimised mode calls `three-hourly` only — it covers 168 hours, so one request supplies
both current conditions and the multi-day outlook. Unoptimised calls `hourly` and `daily`
for finer detail.

Met Office field names are read through candidate lists rather than hard-coded, because
the exact spellings differ between the three feeds and the full schema sits behind a
DataHub account. If a name changes, the "Test connection" button reports which fields went
missing instead of the forecast silently filling with nulls.

### A caveat worth knowing

The Met Office provider is written from the live API's own error responses and published
field conventions, but it has **not been exercised against a real key** — I do not have
one. The authentication, endpoints and error handling are verified; the response parsing
is careful but unproven. Press "Test connection" first: it will tell you if anything is
missing.

---

## Weather warnings

Warnings come from the Met Office public RSS feed, which needs no key. They appear only
when all three of these hold:

1. The Met Office is the selected forecast source — they are a Met Office product, and
   showing them beside an Open-Meteo forecast would misattribute them.
2. Your location is in the UK. The region is derived from your coordinates by matching
   against anchor towns in each of the 16 warning regions; a single centroid per region
   is not accurate enough, since it places Cardiff in South West England.
3. The warning is in force at some point today — active now, or starting later today.
   One that ended this morning or does not begin until Thursday is not shown.

## Setting your location

Three ways, in Settings → Location:

- **Detect my location** — uses your device's GPS when the app is reached over HTTPS or
  localhost, and otherwise works out roughly where you are from your broadband address.
  Either way it proposes a place for you to confirm before anything is saved.
- **Search for a place** — the precise option, and the one to use if detection is off.
- **Enter coordinates** — for when you know exactly what you want.

Browsers only hand out GPS on a secure origin. Served over plain HTTP on the LAN,
`navigator.geolocation` refuses outright with *"Only secure origins are allowed"*, so the
network lookup is the fallback. It is approximate: it resolves to wherever your ISP hands
off traffic, which can be a town or two from where you actually are — the UI says so and
asks you to check. Two different lookup services disagreed by about 80 km on the same
connection during testing.

If you want true device GPS, serve the app over HTTPS and the button will use it
automatically.
