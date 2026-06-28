"""Single-flight ingest orchestration.

The web server stays lightweight by never running ingest in-process. Instead it
calls `request_ingest()`, which marks work pending and spawns a detached worker
(`python -m app.ingest --worker`). The worker holds an exclusive file lock so
only one ingest runs at a time, and it coalesces rapid requests (e.g. a burst of
uploads) into as few runs as possible.

The same worker entrypoint is used by the systemd `wildlens-ingest.service`
(triggered by the folder-drop `.path` unit), so all ingestion paths converge.
"""
from __future__ import annotations

import fcntl
import json
import subprocess
import sys
import time
from pathlib import Path

from .config import settings

_BACKEND_DIR = Path(__file__).resolve().parents[1]


def _lock_path() -> Path:
    return settings.cache_dir / "ingest.lock"


def _pending_path() -> Path:
    return settings.cache_dir / "ingest.pending"


def _status_path() -> Path:
    return settings.cache_dir / "ingest_status.json"


def read_status() -> dict:
    p = _status_path()
    if p.exists():
        try:
            return json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"state": "idle", "started_at": None, "finished_at": None,
            "count": None, "error": None}


def _write_status(**changes) -> None:
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    st = read_status()
    st.update(changes)
    _status_path().write_text(json.dumps(st, indent=2))


def request_ingest() -> None:
    """Mark ingest pending and spawn a detached worker. Safe to call repeatedly."""
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    _pending_path().touch()
    if read_status().get("state") != "running":
        _write_status(state="pending")
    subprocess.Popen(
        [sys.executable, "-m", "app.ingest", "--worker"],
        cwd=str(_BACKEND_DIR),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def run_worker() -> int:
    """Run ingest under an exclusive lock, coalescing pending requests.

    Returns the number of ingest passes performed (0 if another worker held the
    lock — that worker will service our pending marker).
    """
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    lock_f = open(_lock_path(), "w")
    try:
        fcntl.flock(lock_f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock_f.close()
        return 0  # another worker is running; it will pick up the pending marker

    passes = 0
    try:
        from .ingest import build_index

        first = True
        while first or _pending_path().exists():
            first = False
            if _pending_path().exists():
                _pending_path().unlink(missing_ok=True)
            _write_status(state="running", started_at=time.time(), error=None)
            try:
                res = build_index()
                _write_status(state="idle", finished_at=time.time(),
                              count=len(res.photos), error=None)
            except Exception as exc:  # noqa: BLE001
                _write_status(state="error", finished_at=time.time(), error=str(exc))
            passes += 1
    finally:
        fcntl.flock(lock_f, fcntl.LOCK_UN)
        lock_f.close()

    # Close the race window: if a request arrived just as we released the lock,
    # spawn a fresh worker to service it.
    if _pending_path().exists():
        request_ingest()
    return passes
