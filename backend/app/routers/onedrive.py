"""OneDrive import source endpoints (optional feature).

Connect via device code, browse folders, multi-select photos, and import the
originals into data/photos/<trip>/ — then the normal ingest pipeline runs.
Network/download work happens in background threads so requests return quickly;
the frontend polls the *_status endpoints.
"""
from __future__ import annotations

import threading
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from ..config import settings
from ..ingest_runner import request_ingest
from .manage import _safe_filename, _slug, _unique_path

router = APIRouter(prefix="/api/sources/onedrive", tags=["onedrive"])

_connect = {"state": "idle"}          # idle|pending|connected|error
_import = {"state": "idle"}           # idle|running|done|error
_lock = threading.Lock()


def _od():
    """Lazy import keeps the base server free of the source module."""
    from ..sources import onedrive
    return onedrive


@router.get("/status")
def status():
    if not settings.onedrive_configured:
        return {"configured": False, "connected": False}
    od = _od()
    return {"configured": True, "connected": od.is_connected(), "account": od.account_info()}


def _require_configured():
    if not settings.onedrive_configured:
        raise HTTPException(status_code=400, detail="OneDrive not configured")


# --- connect (device code) -------------------------------------------------
def _poll_loop(device_code: str, interval: int, expires_at: float):
    od = _od()
    while time.time() < expires_at:
        time.sleep(max(2, interval))
        try:
            result = od.poll_for_token(device_code)
        except Exception as exc:  # noqa: BLE001
            with _lock:
                _connect.update(state="error", error=str(exc))
            return
        if result == "connected":
            with _lock:
                _connect.update(state="connected", error=None)
            return
        if result != "pending":
            with _lock:
                _connect.update(state="error", error=result)
            return
    with _lock:
        _connect.update(state="error", error="device code expired")


@router.post("/connect")
def connect():
    _require_configured()
    od = _od()
    try:
        dc = od.start_device_code()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    interval = int(dc.get("interval", 5))
    expires_at = time.time() + int(dc.get("expires_in", 900))
    with _lock:
        _connect.clear()
        _connect.update(state="pending", user_code=dc["user_code"],
                        verification_uri=dc["verification_uri"], error=None)
    threading.Thread(target=_poll_loop, args=(dc["device_code"], interval, expires_at),
                     daemon=True).start()
    return {
        "user_code": dc["user_code"],
        "verification_uri": dc["verification_uri"],
        "expires_in": dc.get("expires_in"),
        "message": dc.get("message"),
    }


@router.get("/connect/status")
def connect_status():
    with _lock:
        return dict(_connect)


@router.post("/disconnect")
def disconnect():
    _require_configured()
    _od().disconnect()
    with _lock:
        _connect.clear()
        _connect.update(state="idle")
    return {"connected": False}


# --- browse ----------------------------------------------------------------
@router.get("/browse")
def browse(item_id: str | None = None, cursor: str | None = None, page_size: int = 60):
    _require_configured()
    od = _od()
    try:
        return od.browse(item_id, cursor=cursor, page_size=min(max(page_size, 10), 200))
    except od.NotConnectedError as exc:
        raise HTTPException(status_code=401, detail="OneDrive not connected") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/thumb/{item_id}")
def thumb(item_id: str):
    _require_configured()
    od = _od()
    try:
        data = od.thumbnail_bytes(item_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail="thumbnail unavailable") from exc
    return Response(content=data, media_type="image/jpeg",
                    headers={"Cache-Control": "max-age=3600"})


# --- import ----------------------------------------------------------------
class ImportRequest(BaseModel):
    trip: str = "onedrive"
    item_ids: list[str]


def _import_loop(item_ids: list[str], trip_slug: str):
    od = _od()
    dest_dir = settings.photos_dir / trip_slug
    dest_dir.mkdir(parents=True, exist_ok=True)
    errors: list[dict] = []
    done = 0
    for iid in item_ids:
        try:
            name, url = od.get_item_download(iid)
            target = _unique_path(dest_dir, _safe_filename(name))
            od.stream_to(url, target)
        except Exception as exc:  # noqa: BLE001
            errors.append({"item_id": iid, "error": str(exc)})
        finally:
            done += 1
            with _lock:
                _import.update(done=done, errors=errors)
    with _lock:
        _import.update(state="done", done=done, errors=errors)
    # Hand off to the normal ingest pipeline.
    request_ingest()


@router.post("/import")
def start_import(req: ImportRequest):
    _require_configured()
    if not _od().is_connected():
        raise HTTPException(status_code=401, detail="OneDrive not connected")
    if not req.item_ids:
        raise HTTPException(status_code=400, detail="No items selected")
    with _lock:
        if _import.get("state") == "running":
            raise HTTPException(status_code=409, detail="An import is already running")
        trip_slug = _slug(req.trip, "onedrive")
        _import.clear()
        _import.update(state="running", total=len(req.item_ids), done=0,
                       errors=[], trip=trip_slug)
    threading.Thread(target=_import_loop, args=(req.item_ids, trip_slug),
                     daemon=True).start()
    return {"started": True, "total": len(req.item_ids), "trip": trip_slug}


@router.get("/import/status")
def import_status():
    with _lock:
        return dict(_import)
