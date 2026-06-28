"""Generate demo photos with fake GPS EXIF so wildlens runs without real photos.

Creates data/photos/yellowstone-demo/*.jpg with embedded GPS + capture time
around real Yellowstone landmarks. Safe to delete; nothing here is committed.

Run from the backend/ directory:  python ../scripts/seed_sample.py
"""
from __future__ import annotations
import sys
from datetime import datetime, timedelta
from pathlib import Path
from PIL import Image, ImageDraw
import piexif

# Make `app` importable when run from anywhere.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.config import settings  # noqa: E402

# (name, lat, lon, RGB color) around Yellowstone landmarks.
SAMPLES = [
    ("grand-prismatic", 44.5251, -110.8382, (210, 140, 40)),
    ("old-faithful", 44.4605, -110.8281, (120, 170, 210)),
    ("mammoth-terraces", 44.9766, -110.7036, (220, 220, 200)),
    ("lamar-valley-bison", 44.8979, -110.2260, (110, 140, 80)),
    ("yellowstone-lake", 44.4280, -110.3700, (70, 110, 160)),
    ("lower-falls", 44.7180, -110.4960, (90, 150, 120)),
    ("norris-geyser", 44.7263, -110.7030, (200, 180, 120)),
    ("hayden-valley-elk", 44.6600, -110.4700, (150, 120, 70)),
]


def _deg_to_dms_rational(deg: float):
    deg = abs(deg)
    d = int(deg)
    m_full = (deg - d) * 60
    m = int(m_full)
    s = round((m_full - m) * 60 * 100)
    return ((d, 1), (m, 1), (s, 100))


def _gps_ifd(lat: float, lon: float) -> dict:
    return {
        piexif.GPSIFD.GPSLatitudeRef: "N" if lat >= 0 else "S",
        piexif.GPSIFD.GPSLatitude: _deg_to_dms_rational(lat),
        piexif.GPSIFD.GPSLongitudeRef: "E" if lon >= 0 else "W",
        piexif.GPSIFD.GPSLongitude: _deg_to_dms_rational(lon),
    }


def _make_image(name: str, color: tuple[int, int, int]) -> Image.Image:
    img = Image.new("RGB", (1000, 700), color)
    draw = ImageDraw.Draw(img)
    # Simple "horizon" + label so the demo photos look distinct.
    draw.rectangle([0, 470, 1000, 700], fill=tuple(max(0, c - 50) for c in color))
    draw.ellipse([780, 60, 920, 200], fill=(255, 244, 214))  # sun
    draw.text((30, 30), f"wildlens demo\n{name}", fill=(20, 20, 20))
    return img


def main() -> None:
    out_dir = settings.photos_dir / "yellowstone-demo"
    out_dir.mkdir(parents=True, exist_ok=True)
    base_time = datetime(2025, 6, 21, 9, 0, 0)

    for i, (name, lat, lon, color) in enumerate(SAMPLES):
        img = _make_image(name, color)
        taken = base_time + timedelta(hours=i)
        dt = taken.strftime("%Y:%m:%d %H:%M:%S")
        exif_dict = {
            "0th": {piexif.ImageIFD.DateTime: dt},
            "Exif": {piexif.ExifIFD.DateTimeOriginal: dt},
            "GPS": _gps_ifd(lat, lon),
            "1st": {}, "thumbnail": None,
        }
        exif_bytes = piexif.dump(exif_dict)
        dest = out_dir / f"{i+1:02d}-{name}.jpg"
        img.save(dest, "JPEG", quality=85, exif=exif_bytes)
        print(f"  wrote {dest.name}  ({lat:.4f}, {lon:.4f})")

    print(f"\nDone. {len(SAMPLES)} demo photos in {out_dir}")
    print("Next: cd backend && python -m app.ingest")


if __name__ == "__main__":
    main()
