#!/usr/bin/env bash
# wildlens — systemd user-service installer.
#
# Installs wildlens as a persistent user service on this host (e.g. shumai):
#   - wildlens.service          the API + UI server (auto-restart, starts on boot)
#   - wildlens-watchdog.timer   health check every 2 min, restarts if unhealthy
#   - wildlens-backup.timer     daily backup of the gitignored data/ dir
#   - cloudflare-tunnel.service installed but NOT enabled (opt-in; see README)
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

# Pick a Python: prefer a project venv, fall back to system python3.
if [[ -x "$REPO_ROOT/backend/.venv/bin/python" ]]; then
    PYTHON="$REPO_ROOT/backend/.venv/bin/python"
else
    PYTHON="$(command -v python3)"
fi
echo "==> repo:   $REPO_ROOT"
echo "==> python: $PYTHON"

mkdir -p "$USER_UNITS"
chmod +x "$SCRIPT_DIR"/*.sh

render() {  # $1 = template basename (without .template), renders into USER_UNITS
    local name="$1"
    sed -e "s|__REPO__|$REPO_ROOT|g" -e "s|__PYTHON__|$PYTHON|g" \
        "$SCRIPT_DIR/$name.template" > "$USER_UNITS/$name"
    echo "    rendered $name"
}
copy() {  # $1 = unit filename copied verbatim
    cp "$SCRIPT_DIR/$1" "$USER_UNITS/"
    echo "    copied   $1"
}

echo "==> Installing systemd user units..."
render wildlens.service
render wildlens-watchdog.service
render wildlens-backup.service
copy   wildlens-watchdog.timer
copy   wildlens-backup.timer
copy   cloudflare-tunnel.service

systemctl --user daemon-reload

# Survive logout / run on boot without an active login session.
loginctl enable-linger "$(whoami)" >/dev/null 2>&1 || \
    echo "    [warn] could not enable linger (service won't start at boot without login)"

systemctl --user enable --now wildlens.service
systemctl --user enable --now wildlens-watchdog.timer
systemctl --user enable --now wildlens-backup.timer
# cloudflare-tunnel.service is intentionally NOT enabled — opt in after configuring
# the tunnel (see deploy/README.md "Going public").

echo ""
echo "==> Done. wildlens is running as a user service."
echo "    Status:  systemctl --user status wildlens.service"
echo "    Logs:    journalctl --user -u wildlens.service -f"
echo "    URL:     http://$(hostname -s):${WILDLENS_PORT:-8000}/"
