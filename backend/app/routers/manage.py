"""Management endpoints: photo upload, manual re-ingest, ingest status.

Uploads only write the raw file to disk and then trigger the out-of-process
ingest worker, so the request path stays lightweight (no image decoding here).
"""
from __future__ import annotations

import re
import shutil
import unicodedata
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..config import settings
from ..ingest_runner import read_status, request_ingest

router = APIRouter(prefix="/api", tags=["manage"])

ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".tif", ".tiff",
                ".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm", ".3gp", ".mts", ".hevc"}
MAX_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB per file (videos)


def _slug(value: str, fallback: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    value = re.sub(r"[^A-Za-z0-9 _-]", "", value).strip().replace(" ", "-").lower()
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or fallback


def _safe_filename(name: str) -> str:
    name = Path(name).name  # strip any directory components
    stem = Path(name).stem
    ext = Path(name).suffix.lower()
    stem = re.sub(r"[^A-Za-z0-9 _.-]", "", stem).strip().replace(" ", "_") or "photo"
    return f"{stem}{ext}"


def _unique_path(directory: Path, filename: str) -> Path:
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    stem, ext = Path(filename).stem, Path(filename).suffix
    i = 1
    while True:
        candidate = directory / f"{stem}-{i}{ext}"
        if not candidate.exists():
            return candidate
        i += 1


@router.post("/upload")
async def upload_photos(
    files: list[UploadFile] = File(...),
    trip: str = Form("uploads"),
):
    """Save one or more uploaded photos into data/photos/<trip>/ then re-ingest."""
    trip_slug = _slug(trip, "uploads")
    dest_dir = settings.photos_dir / trip_slug
    dest_dir.mkdir(parents=True, exist_ok=True)

    saved: list[str] = []
    rejected: list[dict] = []

    for upload in files:
        ext = Path(upload.filename or "").suffix.lower()
        if ext not in ALLOWED_EXTS:
            rejected.append({"filename": upload.filename, "reason": "unsupported type"})
            continue

        data = await upload.read()
        if len(data) > MAX_BYTES:
            rejected.append({"filename": upload.filename, "reason": "too large"})
            continue
        if not data:
            rejected.append({"filename": upload.filename, "reason": "empty"})
            continue

        target = _unique_path(dest_dir, _safe_filename(upload.filename or "photo.jpg"))
        target.write_bytes(data)
        saved.append(f"{trip_slug}/{target.name}")

    if not saved:
        raise HTTPException(status_code=400,
                            detail={"message": "No valid images uploaded", "rejected": rejected})

    request_ingest()
    return {"saved": saved, "rejected": rejected, "trip": trip_slug, "ingest": "triggered"}


@router.post("/ingest")
def trigger_ingest():
    """Manually trigger a (coalesced) re-ingest, e.g. after a folder drop."""
    request_ingest()
    return {"ingest": "triggered"}


@router.get("/ingest/status")
def ingest_status():
    return read_status()


@router.post("/photos/delete")
def delete_photos(payload: dict):
    """Move the given photos' originals to data/.trash/ (recoverable), drop their
    cached thumbnail/web versions, then re-ingest.
    """
    ids = payload.get("ids") or []
    if not ids:
        raise HTTPException(status_code=400, detail="No ids provided")

    paths_file = settings.cache_dir / "paths.json"
    path_map = {}
    if paths_file.exists():
        import json
        path_map = json.loads(paths_file.read_text())

    trashed: list[str] = []
    missing: list[str] = []
    for pid in ids:
        src = path_map.get(pid)
        if not src or not Path(src).exists():
            missing.append(pid)
            continue
        src_path = Path(src)
        # Preserve the trip subfolder layout under .trash/.
        try:
            rel = src_path.relative_to(settings.photos_dir)
        except ValueError:
            rel = Path(src_path.name)
        dest = settings.trash_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            dest = dest.with_name(f"{dest.stem}-{pid}{dest.suffix}")
        shutil.move(str(src_path), str(dest))
        (settings.thumbs_dir / f"{pid}.jpg").unlink(missing_ok=True)
        (settings.web_dir / f"{pid}.mp4").unlink(missing_ok=True)
        trashed.append(pid)

    if trashed:
        request_ingest()
    return {"trashed": trashed, "missing": missing, "ingest": "triggered" if trashed else "none"}
