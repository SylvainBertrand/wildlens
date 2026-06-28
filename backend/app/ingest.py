"""Photo ingestion pipeline.

Scans data/photos/<trip>/, extracts EXIF + thumbnails, then ENRICHES each photo
at ingest time (geocoding -> place name, identification provider, Wikipedia fun
facts) and writes a JSON index the runtime server serves verbatim.

Design notes:
- All heavy / network work happens HERE, not in the request path, so the runtime
  server stays tiny and idle-cheap.
- Work is incremental: per-photo results are cached by a content signature, so
  re-running ingest after adding a few photos is fast and avoids re-hitting the
  network (and the Claude CLI).

Run directly:  python -m app.ingest            (from backend/)
               python -m app.ingest --force    (ignore the per-photo cache)
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from PIL import Image, ImageOps

from .config import settings
from .exif_utils import read_metadata
from .identification import get_provider
from .models import GeoPoint, Identification, IdentifiedSubject, Photo, PhotosResponse, Trip

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".tif", ".tiff"}

# Bump when the enrichment logic changes so cached entries are recomputed.
PIPELINE_VERSION = "2"


def _photo_id(trip: str, rel: str) -> str:
    return hashlib.sha1(f"{trip}/{rel}".encode()).hexdigest()[:16]


def _signature(path: Path) -> str:
    st = path.stat()
    flags = f"{int(settings.geocode_enabled)}{int(settings.facts_enabled)}"
    return f"{int(st.st_mtime)}:{st.st_size}:{settings.id_provider}:{flags}:v{PIPELINE_VERSION}"


def _make_thumb(src: Path, dest: Path, size: int) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as img:
        img = ImageOps.exif_transpose(img)  # respect orientation
        img.thumbnail((size, size))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(dest, "JPEG", quality=82)


def _thumb_is_fresh(src: Path, dest: Path) -> bool:
    return dest.exists() and dest.stat().st_mtime >= src.stat().st_mtime


def _iter_images(photos_dir: Path):
    for path in sorted(photos_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTS:
            yield path


def _compose_provider_tag(provider_name: str, used_geo: bool, used_facts: bool) -> str:
    parts: list[str] = []
    if used_geo:
        parts.append("nominatim")
    if provider_name not in ("none", "off", "geo"):
        parts.append(provider_name)
    if used_facts:
        parts.append("wikipedia")
    return "+".join(parts) if parts else "none"


def _enrich(
    path: Path, loc: GeoPoint | None, provider, geocoder, facts
) -> tuple[str | None, str | None, Identification]:
    """Run the enrichment pipeline for one photo (network/CLI work happens here)."""
    subjects: list[IdentifiedSubject] = []
    place_name: str | None = None
    place_detail: str | None = None
    used_geo = False
    used_facts = False

    # 1. Place name from GPS (for the photo header / organizing) + the nearest
    #    notable Wikipedia landmark as a real fun-fact subject.
    geo = None
    if geocoder is not None and loc is not None:
        try:
            geo = geocoder.reverse(loc.lat, loc.lon)
        except Exception as exc:  # noqa: BLE001
            print(f"    ! geocode failed: {exc}")
    if geo:
        used_geo = True
        place_name = geo.get("place_name")
        place_detail = geo.get("detail") or None

    if facts is not None and loc is not None:
        try:
            nf = facts.nearby_fact(loc.lat, loc.lon)
        except Exception as exc:  # noqa: BLE001
            nf = None
            print(f"    ! wikipedia geosearch failed: {exc}")
        if nf:
            used_facts = True
            subjects.append(IdentifiedSubject(
                kind="landmark", label=nf["label"], confidence=1.0,
                fun_fact=nf["fun_fact"], source="wikipedia", url=nf.get("url")))

    # 2. Image-based subjects from the selected provider (none/mock/claude).
    try:
        ctx = {"place_name": place_name, "lat": loc.lat if loc else None,
               "lon": loc.lon if loc else None}
        vision = provider.identify(str(path), ctx)
    except Exception as exc:  # noqa: BLE001
        print(f"    ! identification failed: {exc}")
        vision = Identification(provider=provider.name, subjects=[])

    # 3. Fill missing fun facts for vision subjects from Wikipedia.
    for s in vision.subjects:
        if facts is not None and not s.fun_fact:
            try:
                fact = facts.fact_for([s.label])
            except Exception:  # noqa: BLE001
                fact = None
            if fact:
                used_facts = True
                s.fun_fact = fact["fun_fact"]
                if not s.url:
                    s.url = fact.get("url")
        subjects.append(s)

    tag = _compose_provider_tag(provider.name, used_geo, used_facts)
    return place_name, place_detail, Identification(provider=tag, subjects=subjects)


def build_index(force: bool = False) -> PhotosResponse:
    photos_dir = settings.photos_dir
    photos_dir.mkdir(parents=True, exist_ok=True)
    provider = get_provider(settings.id_provider)

    # Lazy-import enrichment so the runtime server never pulls these in.
    geocoder = facts = None
    if settings.geocode_enabled:
        from .enrich.geocode import NominatimGeocoder
        geocoder = NominatimGeocoder(settings.geocode_cache_path)
    if settings.facts_enabled:
        from .enrich.facts import WikipediaFacts
        facts = WikipediaFacts(settings.facts_cache_path)

    enrich_cache: dict = {}
    if settings.enrich_cache_path.exists() and not force:
        try:
            enrich_cache = json.loads(settings.enrich_cache_path.read_text())
        except (json.JSONDecodeError, OSError):
            enrich_cache = {}

    photos: list[Photo] = []
    trips: dict[str, dict] = {}
    path_map: dict[str, str] = {}
    hits = 0

    for path in _iter_images(photos_dir):
        rel = path.relative_to(photos_dir)
        trip = rel.parts[0] if len(rel.parts) > 1 else "misc"
        pid = _photo_id(trip, str(rel).replace("\\", "/"))

        meta = read_metadata(path)
        loc = GeoPoint(lat=meta["gps"][0], lon=meta["gps"][1]) if meta["gps"] else None

        thumb_path = settings.thumbs_dir / f"{pid}.jpg"
        if not _thumb_is_fresh(path, thumb_path):
            try:
                _make_thumb(path, thumb_path, settings.thumb_size)
            except Exception as exc:  # noqa: BLE001
                print(f"  ! thumbnail failed for {rel}: {exc}")

        # Incremental: reuse cached enrichment when the signature matches.
        sig = _signature(path)
        cached = enrich_cache.get(pid)
        if cached and cached.get("sig") == sig:
            hits += 1
            place_name = cached.get("place_name")
            place_detail = cached.get("place_detail")
            ident = Identification(**cached["identification"])
        else:
            print(f"  + enriching {rel}")
            place_name, place_detail, ident = _enrich(path, loc, provider, geocoder, facts)
            enrich_cache[pid] = {
                "sig": sig,
                "place_name": place_name,
                "place_detail": place_detail,
                "identification": ident.model_dump(),
            }

        photos.append(Photo(
            id=pid, trip=trip, filename=path.name,
            image_url=f"/api/photos/{pid}/image",
            thumb_url=f"/api/photos/{pid}/thumb",
            taken_at=meta["taken_at"], location=loc,
            place_name=place_name, place_detail=place_detail,
            width=meta["width"], height=meta["height"],
            identification=ident,
        ))
        path_map[pid] = str(path.resolve())

        t = trips.setdefault(trip, {"count": 0, "located": 0, "minLat": None,
                                    "minLon": None, "maxLat": None, "maxLon": None})
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
    settings.enrich_cache_path.write_text(
        json.dumps(enrich_cache, indent=2, ensure_ascii=False))
    if geocoder is not None:
        geocoder.save()
    if facts is not None:
        facts.save()

    build_index.last_cache_hits = hits  # type: ignore[attr-defined]
    return result


if __name__ == "__main__":
    if "--worker" in sys.argv:
        # Single-flight worker mode (used by the API trigger + systemd units).
        from .ingest_runner import run_worker
        passes = run_worker()
        print(f"ingest worker: {passes} pass(es)")
        sys.exit(0)

    force = "--force" in sys.argv
    print(f"Ingesting photos from {settings.photos_dir} "
          f"(provider={settings.id_provider}, geocode={settings.geocode_enabled}, "
          f"facts={settings.facts_enabled}{', force' if force else ''}) ...")
    res = build_index(force=force)
    hits = getattr(build_index, "last_cache_hits", 0)
    print(f"Indexed {len(res.photos)} photo(s) across {len(res.trips)} trip(s) "
          f"({hits} reused from cache).")
    for t in res.trips:
        print(f"  - {t.name}: {t.photo_count} photo(s), {t.located_count} geotagged")
    print(f"Index written to {settings.index_path}")
