#!/usr/bin/env bash
# wildlens data backup.
#
# WHY THIS EXISTS: the repo is public, so data/ (your photos + generated
# location metadata) is gitignored and therefore NOT protected by git. This
# script backs up data/ separately so a disk failure on the host doesn't lose
# your photos.
#
# Prefers restic (incremental, deduplicated) if RESTIC_REPOSITORY is set and
# restic is installed; otherwise falls back to a rotated tar.gz archive.
#
# Installed as a systemd user timer (wildlens-backup.timer).
#
# Env:
#   WILDLENS_DATA_DIR     dir to back up        (default: <repo>/data)
#   WILDLENS_BACKUP_DIR   tar fallback target   (default: $HOME/wildlens-backups)
#   WILDLENS_BACKUP_KEEP  tar archives to keep  (default: 7)
#   RESTIC_REPOSITORY     restic repo (optional; enables restic mode)
#   RESTIC_PASSWORD_FILE  restic password file  (default: $HOME/.config/restic/password)
#   HC_PING_URL           healthchecks.io ping URL (optional)
set -euo pipefail

LOG_TAG="wildlens-backup"
log() { echo "[$LOG_TAG] $*"; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

DATA_DIR="${WILDLENS_DATA_DIR:-$REPO_ROOT/data}"
HC_PING_URL="${HC_PING_URL:-}"

ping_hc() {  # $1 = "" | "/fail"
    [[ -n "$HC_PING_URL" ]] || return 0
    curl -fsS --max-time 10 "${HC_PING_URL}${1:-}" >/dev/null 2>&1 || true
}

fail() {
    log "ERROR: $*"
    ping_hc "/fail"
    exit 1
}

[[ -d "$DATA_DIR" ]] || fail "data dir not found: $DATA_DIR"

if [[ -n "${RESTIC_REPOSITORY:-}" ]] && command -v restic >/dev/null 2>&1; then
    export RESTIC_PASSWORD_FILE="${RESTIC_PASSWORD_FILE:-$HOME/.config/restic/password}"
    [[ -f "$RESTIC_PASSWORD_FILE" ]] || fail "RESTIC_PASSWORD_FILE missing: $RESTIC_PASSWORD_FILE"
    log "restic backup of $DATA_DIR -> $RESTIC_REPOSITORY"
    restic backup --tag wildlens "$DATA_DIR" || fail "restic backup failed"
    restic forget --tag wildlens --keep-daily 7 --keep-weekly 4 --prune || log "warn: restic forget/prune failed"
    log "restic backup complete"
else
    BACKUP_DIR="${WILDLENS_BACKUP_DIR:-$HOME/wildlens-backups}"
    KEEP="${WILDLENS_BACKUP_KEEP:-7}"
    mkdir -p "$BACKUP_DIR"
    STAMP="$(date +%Y%m%d-%H%M%S)"
    ARCHIVE="$BACKUP_DIR/wildlens-data-$STAMP.tar.gz"
    log "tar backup of $DATA_DIR -> $ARCHIVE"
    tar -czf "$ARCHIVE" -C "$(dirname "$DATA_DIR")" "$(basename "$DATA_DIR")" || fail "tar failed"
    # Rotate: keep the newest $KEEP archives.
    mapfile -t old < <(ls -1t "$BACKUP_DIR"/wildlens-data-*.tar.gz 2>/dev/null | tail -n +"$((KEEP + 1))")
    for f in "${old[@]:-}"; do [[ -n "$f" ]] && rm -f "$f" && log "pruned $(basename "$f")"; done
    log "tar backup complete ($(du -h "$ARCHIVE" | cut -f1))"
fi

ping_hc ""
log "done"
