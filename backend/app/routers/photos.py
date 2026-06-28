"""Photo + trip API endpoints, plus original/thumbnail image serving."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..config import settings
from ..models import Photo, PhotosResponse

router = APIRouter(prefix="/api", tags=["photos"])


def _load_index() -> PhotosResponse:
    if not settings.index_path.exists():
        return PhotosResponse(trips=[], photos=[])
    data = json.loads(settings.index_path.read_text())
    return PhotosResponse(**data)


def _load_paths() -> dict[str, str]:
    p = settings.cache_dir / "paths.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text())


@router.get("/photos", response_model=PhotosResponse)
def list_photos(trip: str | None = None) -> PhotosResponse:
    index = _load_index()
    if trip:
        photos = [p for p in index.photos if p.trip == trip]
        return PhotosResponse(trips=index.trips, photos=photos)
    return index


@router.get("/photos/{photo_id}", response_model=Photo)
def get_photo(photo_id: str) -> Photo:
    for p in _load_index().photos:
        if p.id == photo_id:
            return p
    raise HTTPException(status_code=404, detail="Photo not found")


@router.get("/photos/{photo_id}/image")
def get_image(photo_id: str):
    # For videos with a transcoded browser-friendly version, serve that so the
    # browser can actually decode it (e.g. HEVC -> H.264).
    web = settings.web_dir / f"{photo_id}.mp4"
    if web.exists():
        return FileResponse(web, media_type="video/mp4")
    src = _load_paths().get(photo_id)
    if not src or not Path(src).exists():
        raise HTTPException(status_code=404, detail="Image file not found")
    return FileResponse(src)


@router.get("/photos/{photo_id}/original")
def get_original(photo_id: str):
    """Always serve the untouched original (for download)."""
    src = _load_paths().get(photo_id)
    if not src or not Path(src).exists():
        raise HTTPException(status_code=404, detail="Original not found")
    return FileResponse(src)


@router.get("/photos/{photo_id}/thumb")
def get_thumb(photo_id: str):
    thumb = settings.thumbs_dir / f"{photo_id}.jpg"
    if not thumb.exists():
        # Fall back to the original if the thumbnail is missing.
        src = _load_paths().get(photo_id)
        if src and Path(src).exists():
            return FileResponse(src)
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    return FileResponse(thumb, media_type="image/jpeg")
