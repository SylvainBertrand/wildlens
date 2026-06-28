#!/usr/bin/env bash
# wildlens watchdog: ping the health endpoint; restart the service if it fails.
# Installed as a systemd user timer (wildlens-watchdog.timer).
set -euo pipefail

HEALTH_URL="${WILDLENS_HEALTH_URL:-http://localhost:8000/api/health}"
SERVICE="wildlens.service"
LOG_TAG="wildlens-watchdog"

log() { echo "[$LOG_TAG] $*"; }

if curl -fsS --max-time 10 "$HEALTH_URL" >/dev/null 2>&1; then
    log "healthy"
    exit 0
fi

log "health check FAILED at $HEALTH_URL — restarting $SERVICE"
systemctl --user restart "$SERVICE" || {
    log "restart command failed"
    exit 1
}

# Give it a moment, then re-check.
sleep 8
if curl -fsS --max-time 10 "$HEALTH_URL" >/dev/null 2>&1; then
    log "recovered after restart"
    exit 0
fi
log "still unhealthy after restart"
exit 1
