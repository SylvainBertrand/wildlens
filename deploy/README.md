# Deployment — wildlens on a LAN host (e.g. `shumai`)

wildlens runs as a **systemd user service**: it starts on boot, restarts on
failure, health-checks itself, and backs up your photos daily. One process
serves both the API and the built frontend.

Patterns here are adapted (proportionately) from the `trading_company` project's
systemd-based deployment.

## Units

| Unit | Purpose |
|------|---------|
| `wildlens.service` | API + UI server on `:8000` (auto-restart, starts on boot) |
| `wildlens-watchdog.timer` → `.service` | Curl `/api/health` every 2 min; restart if unhealthy |
| `wildlens-backup.timer` → `.service` | Daily backup of the **gitignored** `data/` dir at 02:30 |
| `cloudflare-tunnel.service` | Public access (installed, **not enabled** by default) |

> `.service.template` files contain `__REPO__` / `__PYTHON__` placeholders that
> `install.sh` fills in for wherever you cloned the repo.

## First-time setup on shumai

```bash
git clone https://github.com/SylvainBertrand/wildlens.git
cd wildlens

# 1. Python env (a venv keeps the host clean)
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt

# 2. Build the frontend (served by the backend from frontend/dist)
cd frontend && npm install && npm run build && cd ..

# 3. Add photos + ingest
mkdir -p data/photos/<trip>            # copy your photos in
backend/.venv/bin/python -m backend.app.ingest   # or: cd backend && .venv/bin/python -m app.ingest

# 4. Install + start the services
bash deploy/install.sh
```

Open `http://shumai:8000/` from any device on the LAN.

## Day-to-day operations

```bash
# Status / logs
systemctl --user status wildlens.service
journalctl --user -u wildlens.service -f

# Deploy updates (pull, rebuild if frontend changed, re-ingest if photos changed)
git pull
cd frontend && npm run build && cd ..        # only if frontend changed
cd backend && .venv/bin/python -m app.ingest && cd ..   # only if photos changed
systemctl --user restart wildlens.service

# After adding photos
cd backend && .venv/bin/python -m app.ingest
systemctl --user restart wildlens.service    # (restart not strictly needed; index is read per-request)

# Timers
systemctl --user list-timers "wildlens*"
```

## Backups (important — photos are NOT in git)

`data/` is gitignored, so your photos and location metadata are **not** protected
by GitHub. `wildlens-backup.timer` runs `deploy/wildlens-backup.sh` daily:

- Default: rotated `tar.gz` archives in `~/wildlens-backups` (keeps 7).
- If you set `RESTIC_REPOSITORY` (and install restic), it uses restic instead
  (incremental, deduplicated, with retention).

Run a backup now / restore:

```bash
bash deploy/wildlens-backup.sh                       # manual backup
tar -xzf ~/wildlens-backups/wildlens-data-*.tar.gz -C /tmp/restore   # inspect/restore
```

Configure via `.env` (see repo `.env.example`): `WILDLENS_BACKUP_DIR`,
`WILDLENS_BACKUP_KEEP`, `RESTIC_REPOSITORY`, `HC_PING_URL`.

## Going public (Cloudflare Tunnel)

No port-forwarding or exposed IP needed.

```bash
# Install cloudflared, then:
cloudflared tunnel login
cloudflared tunnel create wildlens
cloudflared tunnel route dns wildlens wildlens.example.com
# point ~/.cloudflared/config.yml ingress at http://localhost:8000
systemctl --user enable --now cloudflare-tunnel.service
```

Before exposing publicly, consider adding authentication (e.g. Cloudflare Access
in front of the tunnel) since wildlens has no built-in auth yet.

## Uninstall

```bash
systemctl --user disable --now wildlens.service wildlens-watchdog.timer \
    wildlens-backup.timer cloudflare-tunnel.service
rm ~/.config/systemd/user/wildlens*.service ~/.config/systemd/user/wildlens*.timer \
   ~/.config/systemd/user/cloudflare-tunnel.service
systemctl --user daemon-reload
```
