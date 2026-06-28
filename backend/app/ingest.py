"""Photo ingestion: scan data/photos/<trip>/, extract EXIF + thumbnails,
run identification, and build a JSON index the API serves from.

Run directly:  python -m app.ingest   (from the backend/ directory)
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageOps

from .config import settings
from .exif_utils import read_metadata
from .identification import get_provider
from .models import GeoPoint, Photo, PhotosResponse, Trip

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".tif", ".tiff"}


def _photo_id(trip: str, rel: str) -> str:
    return hashlib.sha1(f"{trip}/{rel}".encode()).hexdigest()[:16]


def _make_thumb(src: Path, dest: Path, size: int) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as img:
        img = ImageOps.exif_transpose(img)  # respect orientation
        img.thumbnail((size, size))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(dest, "JPEG", quality=82)


def _iter_images(photos_dir: Path):
    for path in sorted(photos_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTS:
            yield path


def build_index(run_identification: bool = True) -> PhotosResponse:
    photos_dir = settings.photos_dir
    photos_dir.mkdir(parents=True, exist_ok=True)
    provider = get_provider(settings.id_provider)

    photos: list[Photo] = []
    trips: dict[str, dict] = {}
    path_map: dict[str, str] = {}

    for path in _iter_images(photos_dir):
        rel = path.relative_to(photos_dir)
        # Trip = first path segment, or "misc" if photo sits directly in photos/.
        trip = rel.parts[0] if len(rel.parts) > 1 else "misc"
        rel_str = str(rel).replace("\\", "/")
        pid = _photo_id(trip, rel_str)

        meta = read_metadata(path)
        thumb_path = settings.thumbs_dir / f"{pid}.jpg"
        try:
            _make_thumb(path, thumb_path, settings.thumb_size)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! thumbnail failed for {rel_str}: {exc}")

        loc = None
        if meta["gps"]:
            loc = GeoPoint(lat=meta["gps"][0], lon=meta["gps"][1])

        ident = None
        if run_identification:
            try:
                ctx = {"lat": loc.lat, "lon": loc.lon} if loc else {}
                ident = provider.identify(str(path), ctx)
            except Exception as exc:  # noqa: BLE001
                print(f"  ! identification failed for {rel_str}: {exc}")

        photo = Photo(
            id=pid,
            trip=trip,
            filename=path.name,
            image_url=f"/api/photos/{pid}/image",
            thumb_url=f"/api/photos/{pid}/thumb",
            taken_at=meta["taken_at"],
            location=loc,
            width=meta["width"],
            height=meta["height"],
            identification=ident,
        )
        photos.append(photo)
        path_map[pid] = str(path.resolve())

        t = trips.setdefault(trip, {"count": 0, "located": 0,
                                    "minLat": None, "minLon": None,
                                    "maxLat": None, "maxLon": None})
        t["count"] += 1
        if loc:
            t["located"] += 1
            t["minLat"] = loc.lat if t["minLat"] is None else min(t["minLat"], loc.lat)
            t["maxLat"] = loc.lat if t["maxLat"] is None else max(t["maxLat"], loc.lat)
            t["minLon"] = loc.lon if t["minLon"] is None else min(t["minLon"], loc.lon)
            t["maxLon"] = loc.lon if t["maxLon"] is None else max(t["maxLon"], loc.lon)

    trip_models = []
    for name, t in sorted(trips.items()):
        bounds = None
        if t["located"]:
            bounds = {"minLat": t["minLat"], "minLon": t["minLon"],
                      "maxLat": t["maxLat"], "maxLon": t["maxLon"]}
        trip_models.append(Trip(name=name, photo_count=t["count"],
                                located_count=t["located"], bounds=bounds))

    result = PhotosResponse(trips=trip_models, photos=photos)

    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    settings.index_path.write_text(result.model_dump_json(indent=2))
    (settings.cache_dir / "paths.json").write_text(json.dumps(path_map, indent=2))
    return result


if __name__ == "__main__":
    print(f"Ingesting photos from {settings.photos_dir} ...")
    res = build_index()
    print(f"Indexed {len(res.photos)} photo(s) across {len(res.trips)} trip(s).")
    for t in res.trips:
        print(f"  - {t.name}: {t.photo_count} photo(s), {t.located_count} geotagged")
    print(f"Index written to {settings.index_path}")
