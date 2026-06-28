# Contributing to wildlens

## Project layout

- `backend/` — FastAPI app + photo ingest pipeline (Python)
- `frontend/` — Vite + React + Leaflet UI
- `deploy/` — systemd units + scripts to run wildlens on a LAN host
- `scripts/` — helper scripts (e.g. demo data generation)
- `data/` — **gitignored**; your photos + generated metadata live here only

## Backend dev

```bash
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"        # installs runtime + dev deps from pyproject.toml

# Run the API (with demo data)
python ../scripts/seed_sample.py
python -m app.ingest
python -m app.main             # http://localhost:8000

# Lint + tests
ruff check app tests
pytest -q
```

The identification layer is **pluggable** (`app/identification/`). To add a real
provider: implement the `IdentificationProvider` protocol in `base.py`, register
it in `registry.py`, and select it via `WILDLENS_ID_PROVIDER`. Don't change the
API or ingest code.

## Frontend dev

```bash
cd frontend
npm install
npm run dev                    # http://localhost:5173 (proxies /api to :8000)
npm run build                  # production build served by the backend
```

## Privacy rules (the repo is PUBLIC)

- Never commit anything under `data/` (photos, GPS metadata, thumbnails).
- Never commit secrets — use `.env` (gitignored); document keys in `.env.example`.

## Conventions

- Python: `ruff` (config in `backend/pyproject.toml`), type hints, small modules.
- Keep changes surgical; add a test when changing ingest/identification logic.
- Tests are marked `@pytest.mark.unit` (pure logic, no network/I/O beyond tmp files).
