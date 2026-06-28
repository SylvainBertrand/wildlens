"""EXIF helpers: extract GPS coordinates and capture time from images."""
from __future__ import annotations

from datetime import datetime

from PIL import ExifTags, Image

_GPS_IFD = next(k for k, v in ExifTags.TAGS.items() if v == "GPSInfo")
_GPS_TAGS = ExifTags.GPSTAGS
_TAGS = ExifTags.TAGS


def _to_degrees(value) -> float:
    """Convert EXIF rational (d, m, s) to decimal degrees."""
    d, m, s = value
    return float(d) + float(m) / 60.0 + float(s) / 3600.0


def extract_gps(exif) -> tuple[float, float] | None:
    if not exif:
        return None
    # GPS lives in its own sub-IFD; Pillow exposes it via get_ifd().
    gps = None
    try:
        gps = exif.get_ifd(_GPS_IFD)
    except Exception:
        gps = None
    if not gps:
        raw = exif.get(_GPS_IFD)
        gps = raw if isinstance(raw, dict) else None
    if not gps:
        return None
    named = {_GPS_TAGS.get(k, k): v for k, v in gps.items()}
    lat = named.get("GPSLatitude")
    lon = named.get("GPSLongitude")
    lat_ref = named.get("GPSLatitudeRef", "N")
    lon_ref = named.get("GPSLongitudeRef", "E")
    if lat is None or lon is None:
        return None
    try:
        lat_d = _to_degrees(lat)
        lon_d = _to_degrees(lon)
    except (TypeError, ValueError):
        return None
    if str(lat_ref).upper().startswith("S"):
        lat_d = -lat_d
    if str(lon_ref).upper().startswith("W"):
        lon_d = -lon_d
    return (lat_d, lon_d)


def extract_taken_at(exif) -> str | None:
    if not exif:
        return None
    name_to_id = {v: k for k, v in _TAGS.items()}
    for field in ("DateTimeOriginal", "DateTimeDigitized", "DateTime"):
        tag = name_to_id.get(field)
        if tag and tag in exif:
            raw = exif.get(tag)
            try:
                dt = datetime.strptime(str(raw), "%Y:%m:%d %H:%M:%S")
                return dt.isoformat()
            except ValueError:
                continue
    return None


def read_metadata(path) -> dict:
    """Return {gps, taken_at, width, height} for an image path."""
    out: dict = {"gps": None, "taken_at": None, "width": None, "height": None}
    with Image.open(path) as img:
        out["width"], out["height"] = img.size
        try:
            exif = img.getexif()
            # Merge the EXIF sub-IFD so DateTimeOriginal is reachable too.
            merged = dict(exif)
            try:
                for k, v in exif.get_ifd(0x8769).items():  # ExifOffset sub-IFD
                    merged.setdefault(k, v)
            except Exception:
                pass
            out["gps"] = extract_gps(exif)
            out["taken_at"] = extract_taken_at(merged)
        except Exception:
            pass
    return out
