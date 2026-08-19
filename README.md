# Outfits

A self-hosted wardrobe manager running on a Raspberry Pi. Photograph what you own,
build outfits, get suggestions scored against the London weather, and keep track of
what needs washing.

**Live at [http://outfits.local/](http://outfits.local/)** on the local network.

---

## What it does

**Photo wardrobe.** Upload or photograph an item and it is catalogued. Colours are
extracted from the photo automatically — this is plain image processing, not AI, so it
works with no API key and no model. With a Gemini key configured it also fills in
category, material, pattern, warmth and formality for you to confirm.

**Weather-aware suggestions.** Open-Meteo (free, no key) supplies the feels-like
temperature, and outfits are scored on total insulation against it, plus rain, wind,
occasion and colour harmony. Every suggestion shows its reasoning, so a bad suggestion
tells you which dial to turn.

**It learns how you feel the cold.** Rate a wear "too hot", "just right" or "too cold"
and your personal warmth offset shifts. The app converges on how *you* experience 12 °C
rather than assuming an average body.

**Washing that understands garments.** Each item has its own wear threshold — socks
after one wear, a shirt after two, a coat after twenty-five. Once things are dirty the
laundry view groups them into loads that can actually go in the machine together, split
by temperature and colour, with wool and delicates kept separate. Care instructions can
be typed in or read from a photograph of the care label.

**Jewellery and accessories** are first-class: they flow through outfits and analytics
like everything else, they never enter the wash pile, and metal tones are treated as
metal rather than as a clashing colour.

**Analytics.** Most and least worn, cost per wear, things untouched for 90 days, colour
distribution, repeated pairings, laundry history, and gaps limiting your suggestions.

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
