#!/usr/bin/env bash
# wildlens — systemd user-service installer (lightweight, socket-activated).
#
# Installs wildlens to run on this host (e.g. shumai) with a near-zero idle
# footprint:
#   - wildlens.socket           always-listening socket on :8000
#   - wildlens.service          started on first request, EXITS after 10 min idle
#                               (socket restarts it instantly on the next request)
#   - wildlens-backup.timer     daily backup of the gitignored data/ dir
#   - cloudflare-tunnel.service installed but NOT enabled (opt-in; see README)
#
# Also installed but NOT enabled (only useful in always-on mode, since their
# health pings would keep the idle-exit from ever firing):
#   - wildlens-watchdog.timer
#
# Prerequisites:
#   - Python deps installed (a venv at backend/.venv is recommended)
#   - Frontend built:  cd frontend && npm install && npm run build
#   - Photos ingested: cd backend && python -m app.ingest
#
# Usage:  bash deploy/install.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
USER_UNITS="$HOME/.config/systemd/user"

if [[ -x "$REPO_ROOT/backend/.venv/bin/python" ]]; then
    PYTHON="$REPO_ROOT/backend/.venv/bin/python"
else
    PYTHON="$(command -v python3)"
fi
echo "==> repo:   $REPO_ROOT"
echo "==> python: $PYTHON"

mkdir -p "$USER_UNITS"
chmod +x "$SCRIPT_DIR"/*.sh

render() {  # $1 = template basename (without .template) -> USER_UNITS
    sed -e "s|__REPO__|$REPO_ROOT|g" -e "s|__PYTHON__|$PYTHON|g" \
        "$SCRIPT_DIR/$1.template" > "$USER_UNITS/$1"
    echo "    rendered $1"
}
copy() { cp "$SCRIPT_DIR/$1" "$USER_UNITS/"; echo "    copied   $1"; }

echo "==> Installing systemd user units..."
copy   wildlens.socket
render wildlens.service
render wildlens-backup.service
copy   wildlens-backup.timer
render wildlens-watchdog.service       # installed for always-on mode, not enabled
copy   wildlens-watchdog.timer
render wildlens-ingest.service         # oneshot worker (triggered, not boot-enabled)
render wildlens-ingest.path            # folder-drop auto-ingest watcher
copy   cloudflare-tunnel.service

systemctl --user daemon-reload

# Survive logout / run on boot without an active login session.
loginctl enable-linger "$(whoami)" >/dev/null 2>&1 || \
    echo "    [warn] could not enable linger (won't start at boot without login)"

# Socket activation: enable the SOCKET (not the service). The service starts on
# the first request and exits when idle.
systemctl --user enable --now wildlens.socket
systemctl --user enable --now wildlens-backup.timer
# Folder-drop auto-ingest: watch data/photos for new trip folders.
systemctl --user enable --now wildlens-ingest.path

echo ""
echo "==> Done. wildlens is socket-activated and idle-exiting."
echo "    It starts on first request and stops after ~10 min idle (near-zero idle cost)."
echo "    Drop a trip folder into data/photos/ and it auto-ingests; or use the"
echo "    in-app upload, or:  systemctl --user start wildlens-ingest.service"
echo "    Status:  systemctl --user status wildlens.socket wildlens.service"
echo "    Logs:    journalctl --user -u wildlens.service -f"
echo "    URL:     http://$(hostname -s):8000/"
echo ""
echo "Always-on instead of idle-exiting? Set WILDLENS_IDLE_TIMEOUT=0 in .env, then:"
echo "    systemctl --user enable --now wildlens.service wildlens-watchdog.timer"
