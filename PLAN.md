# Outfits — Wardrobe Manager

Self-hosted wardrobe app on the Raspberry Pi. Photo-based inventory, outfit building,
weather-aware suggestions, wear + washing tracking, analytics.

> **Status: built and running.** All five phases are complete and the app is live at
> http://outfits.local/. See [README.md](README.md) for how to use and operate it.
> This document is kept for the deployment research behind the network design —
> the measurements in section 1 are why the app runs the way it does.

---

## 1. Deployment: how it coexists with FlatBrain

### The constraint (measured, not assumed)

FlatBrain's Node process binds `*:80` — the wildcard address, every interface.
Verified by test: binding a *specific* IP on port 80 fails with `EADDRINUSE` even with
`SO_REUSEADDR` set on both sockets. There is no way to share port 80 on this host.

### The solution: separate network namespace

Outfits runs inside its own Linux network namespace with its own MAC address and its own
LAN IP. Inside that namespace, port 80 is an entirely separate port — no conflict is even
possible, because it is a different network stack.

```
                    eth0 (physical)
                          |
        +-----------------+-----------------+
        |                                   |
   host stack                        macvlan "outfits0"
   192.168.86.28                     192.168.86.251
   flatbrain.local                   outfits.local
   node :80  (UNTOUCHED)             uvicorn :80
                                     [netns: outfits]
```

**FlatBrain is not modified in any way.** Not its code, not its port, not its systemd unit,
not its avahi service file, not its hostname. `http://flatbrain.local/` keeps resolving to
192.168.86.28 and keeps being served by the same Node process on the same port 80.

### Verified working

All of the following were tested on this Pi and passed:

| Test | Result |
| --- | --- |
| App on `192.168.86.251:80` inside netns | 200, served by the netns process |
| `http://192.168.86.28/` during that | 200, FlatBrain |
| `http://flatbrain.local/` during that | 200, FlatBrain |
| Outbound internet from inside netns (Open-Meteo) | works |
| `avahi-publish -a -R outfits.local 192.168.86.251` | resolves via `avahi-resolve` and `getent` |
| `flatbrain.local` after publishing | still 192.168.86.28 |

Everything was torn down after testing; the host is currently in its original state.

### The three systemd units

1. **`outfits-netns.service`** (oneshot) — creates namespace `outfits`, creates macvlan
   `outfits0` on `eth0`, moves it into the namespace, assigns `192.168.86.251/24`, sets the
   default route via `192.168.86.1`.
2. **`outfits-mdns.service`** — runs `avahi-publish -a -R outfits.local 192.168.86.251` in the
   foreground with `Restart=always`. Holds the mDNS record for as long as it runs. Publishes an
   additional name; changes nothing about the existing `flatbrain.local` record.
3. **`outfits.service`** — the app, with `NetworkNamespacePath=/var/run/netns/outfits` and
   `AmbientCapabilities=CAP_NET_BIND_SERVICE`, running as user `pi`.

### Details that matter

- **IP choice**: `192.168.86.251` is free (verified by ping and arping) and sits above the
  typical Nest WiFi DHCP pool (.20–.249). Confirm on the router that .251 is outside the pool,
  or add a reservation for the macvlan MAC.
- **DNS inside the namespace**: needs `/etc/netns/outfits/resolv.conf`. This is a
  namespace-private file — the host's `/etc/resolv.conf` is not touched.
- **Host cannot reach 192.168.86.251 by default** (macvlan parent/child isolation). Phones and
  laptops on the LAN reach it fine. For testing from the Pi itself, use
  `sudo ip netns exec outfits curl http://localhost/`. A host-side macvlan would also work but
  would make avahi advertise a second IP for `flatbrain.local` — avoided deliberately.
- **Router sees a second MAC** on the wired port. Harmless; it appears as one extra device.
- **Android mDNS** is unreliable in some browsers. Fallback: bookmark `http://192.168.86.251/`
  or add a DNS entry on the router.
- **Rollback** is `systemctl disable --now` on the three units plus `ip netns del outfits`.
  Nothing else on the Pi is altered.

---

## 2. Stack

Chosen for a single user on a Pi 4: no Postgres, no Redis, no Docker.

- **Backend**: FastAPI + uvicorn (Python 3.13, already installed)
- **Database**: SQLite in WAL mode, one file
- **Images**: Pillow — EXIF rotation, downscale to 1600px, thumbnails, colour palette extraction
- **Frontend**: React + Vite + Tailwind, built to static files and served by FastAPI
- **Jobs**: a `jobs` table plus a background worker thread. No queue service.
- **AI**: Gemini API, optional. No local model (per decision). The provider layer stays
  pluggable so a local tier can be added later without touching call sites.

Expected footprint: ~150 MB RAM idle, one process, one `.db` file. Backup is a
`sqlite3 .backup` plus an rsync of the photos directory.

The reference project (Anyesh/wardrowbe) uses Next.js + FastAPI + Postgres + Redis + Docker.
Its *ideas* are worth borrowing — Open-Meteo for weather, provider-agnostic AI, wear logging.
Its infrastructure is roughly 1.5 GB of RAM for features a single user does not need.

---

## 3. Data model

```
items              id, name, category, subcategory, brand, material, pattern,
                   colour_primary, colour_secondary, colour_palette (json),
                   warmth (1-10), formality (1-5), seasons, wind_proof, water_proof,
                   purchase_date, price, image_path, cutout_path, thumb_path,
                   status, wears_since_wash, wash_after_wears, total_wears,
                   last_worn, notes, ai_provider, ai_confidence, is_active

care_instructions  item_id, wash_temp, wash_cycle, tumble_dry, iron_temp,
                   bleach, dry_clean, hand_wash_only, raw_symbols, source

outfits            id, name, occasion, is_favourite, created_at
outfit_items       outfit_id, item_id, layer

wear_log           id, worn_on, outfit_id, occasion, comfort_rating,
                   temp_c, apparent_c, condition, notes
wear_log_items     wear_log_id, item_id

wash_batches       id, washed_on, program, temp_c, notes
wash_batch_items   batch_id, item_id

tags / item_tags   free-form labels
settings           key/value — AI provider, API key, location, units
jobs               id, item_id, kind, status, payload, result, error
```

**Categories** cover clothing *and* accessories: top, bottom, dress, outerwear, footwear,
underwear, sock, headwear, scarf, glove, belt, bag, glasses, watch, jewellery. Accessories and
jewellery simply have null wash fields and sit in the `accessory` / `jewellery` layer, so they
flow through outfit building and analytics like everything else.

**Layers** for the outfit builder: base → bottom → top → mid → outer → footwear → accessory →
jewellery.

---

## 4. Feature design

### Photo pipeline

Upload → EXIF auto-rotate → downscale to 1600 px → thumbnail → **colour palette extracted with
Pillow quantisation, no AI involved** → manual tag form pre-filled with the detected colours.
With Gemini enabled, the same upload also queues a job that fills category, subcategory,
pattern, material, warmth estimate and formality, which you then confirm or correct.

### Washing engine

Each item has `wash_after_wears`, defaulted by category — socks and underwear 1, shirts 2,
jumpers 5, jeans 8, coats 25 — and overridable per item. Logging a wear increments
`wears_since_wash`; crossing the threshold flips status to **needs wash**. Some items get
**air out** instead. A laundry view groups everything currently dirty into compatible loads by
wash temperature and colour group, so the output is "run a 30° darks load, these 12 items"
rather than a flat list.

Care instructions are entered manually, or read from a photo of the care label by Gemini
(symbols → temperature, cycle, tumble dry, iron, bleach, dry clean).

### Weather recommendations

Open-Meteo, free and keyless, London, cached hourly. Verified reachable from inside the
namespace. It returns `apparent_temperature` — feels-like — which is the right input here.

Scoring: each item carries a warmth value; an outfit's total warmth is compared against the
feels-like temperature, with rain and wind flags pulling in waterproof and windproof items.
**The calibration is personal**: your comfort rating after each wear ("too hot / right / too
cold") shifts your own warmth curve over time, so the app learns that you run warm rather than
assuming a generic body. Additional filters for occasion and colour harmony, and dirty items
are excluded by default.

### Analytics

Most and least worn, cost-per-wear, never worn in 90+ days, colour distribution, most frequent
item combinations, wash-load counts, and wardrobe gaps.

### AI tiers

- **None** — manual tagging, plus automatic colour extraction. Fully functional wardrobe.
- **Gemini** — API key in settings; photo tagging, care-label reading, background cutout.

Every AI call degrades to the manual path on failure or missing key. The app never hard-depends
on AI being present.

---

## 5. Build phases — all complete

| Phase | Scope | Done |
| --- | --- | --- |
| 0 | Network namespace, three systemd units, skeleton on `outfits.local` | yes |
| 1 | Schema, item CRUD, photo pipeline, colour extraction, gallery | yes |
| 2 | Wear logging, wear counters, care instructions, laundry batching | yes |
| 3 | Outfit builder, Open-Meteo, warmth scoring, personal calibration | yes |
| 4 | Gemini provider, analytics dashboard, PWA, backup script | yes |

## 6. What changed from the plan

Five things were found by testing rather than anticipated, and the design changed:

1. **Colour naming moved to CIE Lab.** The planned redmean distance named a grey marl
   t-shirt "khaki" and tan leather "olive". Lab fixed all 21 reference cases.
2. **Rain is scored over the hours still ahead.** Taking the day's maximum reported
   "100% rain" at teatime under clear skies, because it had rained at 4am — and pushed
   the recommender into a raincoat.
3. **Warm accessories are gated on absolute temperature.** Arithmetic alone put a beanie
   on a 23 °C outfit whenever the warmth total sat below target.
4. **Logging a past-dated wear no longer stamps today's weather on it.** That silently
   poisoned the comfort calibration, which learns from the gap between what you wore and
   how warm it actually was.
5. **`index.html` is served `no-cache`.** It names the hashed asset bundles, so a cached
   copy pinned the browser to a previous build permanently.

## 7. Open items

- Confirm `192.168.86.251` sits outside the router's DHCP pool, or reserve it for the
  macvlan MAC. It was free at install time (checked by ping and arping).
- Gemini is unconfigured. The app is fully usable without it; add a key in Settings to
  turn on automatic tagging and care-label reading.
- The phone layout is built responsively and its breakpoints are active, but it was not
  viewed at phone width — the test browser's viewport could not be resized.
