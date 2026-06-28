"""Management endpoints: photo upload, manual re-ingest, ingest status.

Uploads only write the raw file to disk and then trigger the out-of-process
ingest worker, so the request path stays lightweight (no image decoding here).
"""
from __future__ import annotations

import re
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
