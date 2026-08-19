# Outfits — Wardrobe Manager

Self-hosted wardrobe app on the Raspberry Pi. Photo-based inventory, outfit building,
weather-aware suggestions, wear + washing tracking, analytics.

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

## 5. Build phases

### Phase 0 — Network + skeleton · ~1.5 h
The novel part, proven first. Three systemd units, hello-world FastAPI answering on
`http://outfits.local/`, and a check that `flatbrain.local` is untouched.

### Phase 1 — Wardrobe core, zero AI · ~6-8 h
Schema and migrations, item CRUD, photo upload pipeline, colour extraction, manual tag form,
gallery grid with filters and search. **At the end of this phase the app is already useful.**

### Phase 2 — Wear + washing · ~5-6 h
Wear logging, wear counters and status transitions, care instructions, the laundry batching
view, "due for washing" list, wash history.

### Phase 3 — Outfits + weather · ~6-8 h
Layer-based outfit builder, saved outfits, Open-Meteo integration, warmth scoring, personal
calibration from comfort ratings, occasion and colour filters.

### Phase 4 — Gemini, analytics, PWA · ~7-9 h
Provider abstraction and settings screen, photo tagging jobs, care-label reading, the analytics
dashboard, PWA manifest and service worker so it installs on your phone with camera capture,
and a backup script.

**Total: roughly 30-40 hours of build time**, in phases that each end with something working.

---

## 6. Open items

- Confirm `192.168.86.251` is outside the router's DHCP pool.
- Decide whether Gemini gets configured now or after Phase 3 (the app is fully usable without it).
