# wildlens

A small, reusable web app to relive your trips: drop in your vacation photos and
explore them on an interactive map, organized by location. Each photo can show
identified landmarks, flora & fauna, and fun facts. Built to run on your LAN
first (e.g. on a home server), and go public later.

> **Privacy:** this repo is public, so **your photos and their location data are
> never committed**. Everything under `data/` is gitignored — it lives only on
> the machine running wildlens.

## Features

- 📍 **Map view** — photos placed by GPS (EXIF) as thumbnail pins (Leaflet + OpenStreetMap, no API key)
- 🗂️ **Trips** — organize photos as `data/photos/<trip>/...`, reused across vacations
- 🏞️ **Real place names & fun facts (no API keys)** — reverse-geocoding via
  OpenStreetMap **Nominatim** + the nearest notable **Wikipedia** landmark with a
  real summary and a "read more" link
- 🔎 **Pluggable image identification** — `none` (default, place + facts only),
  `mock` (demo subjects), or `claude` (real flora/fauna/landmark ID via your
  Claude CLI subscription — no separate key). New providers drop in without
  touching the API.
- 🪶 **Lightweight when idle** — all heavy work runs at ingest time; the runtime
  server is tiny and (under systemd) socket-activates and **exits when idle**, so
  it uses near-zero CPU/RAM when nobody's browsing
- 🖼️ **Detail view** — full photo, place, capture time, coordinates, fun facts

## Tech stack

- **Backend:** Python + FastAPI (EXIF/GPS extraction, thumbnails, enrichment, JSON index, REST API)
- **Frontend:** React (Vite) + react-leaflet
- **Map tiles:** OpenStreetMap · **Geocoding:** Nominatim · **Facts:** Wikipedia (all key-free)

## Layout

```
backend/        FastAPI app + photo ingest pipeline
  app/
    ingest.py            scan photos -> EXIF/GPS + thumbnails -> enrich -> data/cache/index.json
    enrich/              ingest-time geocoding (Nominatim) + facts (Wikipedia); cached
    identification/      pluggable providers (none / mock / claude)
    routers/photos.py    REST API + image/thumbnail serving (lightweight runtime)
frontend/       Vite + React + Leaflet map UI
deploy/         systemd units (socket activation + idle exit), backup, install.sh
scripts/        seed_sample.py (demo photos with fake GPS)
data/           GITIGNORED: photos/<trip>/ + cache/ (thumbnails, index, geo/facts caches)
```

## Quick start (development)

Requirements: Python 3.11+, Node 22.12+ (or 20.19+).

```bash
# 1. Backend deps
cd backend
python3 -m pip install -r requirements.txt

# 2. (Optional) generate demo photos to see it working immediately
python ../scripts/seed_sample.py

# 3. Ingest photos -> builds thumbnails + index
python -m app.ingest

# 4. Run the API (LAN-reachable on :8000)
python -m app.main
```

In another terminal:

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173 (also reachable on your LAN IP)
```

Open the dev URL. The Vite dev server proxies `/api` to the backend on `:8000`.

### Adding your own photos

```bash
mkdir -p data/photos/my-trip
cp /path/to/photos/*.jpg data/photos/my-trip/
cd backend && python -m app.ingest      # re-run after adding photos
```

Photos need GPS EXIF data to appear on the map (most phone photos have it).
Photos without GPS are still indexed and listed in the sidebar.

## Production / deploying to a LAN host (e.g. `shumai`)

wildlens runs as a **systemd user service** that starts on boot, auto-restarts,
health-checks itself (watchdog), and backs up your photos daily. One process
serves both the API and the built frontend. See **[`deploy/README.md`](deploy/README.md)**
for the full guide; the short version:

```bash
git clone https://github.com/SylvainBertrand/wildlens.git
cd wildlens
python3 -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements.txt
cd frontend && npm install && npm run build && cd ..   # built UI served by backend
# add photos under data/photos/<trip>/ then:
cd backend && .venv/bin/python -m app.ingest && cd ..
bash deploy/install.sh                                  # installs + starts the service
# open http://shumai:8000/
```

Configuration is via environment variables or a `.env` file (see `.env.example`):
`WILDLENS_PORT`, `WILDLENS_IDLE_TIMEOUT`, `WILDLENS_ID_PROVIDER` (`none`/`mock`/`claude`),
`WILDLENS_GEOCODE_ENABLED`, `WILDLENS_FACTS_ENABLED`, `WILDLENS_THUMB_SIZE`, plus
backup settings (`WILDLENS_BACKUP_DIR`, `RESTIC_REPOSITORY`, ...).

> **Backups:** because `data/` is gitignored, your photos are **not** in GitHub.
> The deploy installs a daily backup timer for `data/` — see `deploy/README.md`.

> **Going public later:** a `cloudflare-tunnel.service` is included (installed but
> not enabled) so you can expose wildlens without port-forwarding. Add auth first.

## Roadmap

- **Phase 1 (done):** map + photo pipeline + pluggable identification + privacy-safe data handling
- **Phase 2 (done):** real, key-free enrichment + lightweight runtime
  - reverse geocoding (OpenStreetMap Nominatim) for place names
  - nearest-landmark fun facts via Wikipedia geosearch (with "read more" links)
  - optional Claude CLI provider for real flora/fauna/landmark ID (uses an existing subscription)
  - socket activation + idle auto-shutdown for near-zero idle CPU/RAM
  - incremental ingest (skip unchanged photos; cached geocode/facts lookups)
- **Phase 3 (next):** public hosting (Cloudflare Tunnel + auth), photo upload UI,
  marker clustering, optional local CLIP provider for fully-offline vision

## License

TBD.
