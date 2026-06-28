"""Tests for the EXIF/GPS extraction and the ingest pipeline.

These exercise the round-trip: write a JPEG with GPS EXIF (as seed_sample does)
-> read it back -> build the index.
"""
from __future__ import annotations

from pathlib import Path

import piexif
import pytest
from PIL import Image

from app.exif_utils import read_metadata


def _write_jpeg_with_gps(path: Path, lat: float, lon: float, when: str = "2025:06:21 09:00:00"):
    img = Image.new("RGB", (64, 48), (120, 160, 90))

    def dms(deg: float):
        deg = abs(deg)
        d = int(deg)
        m = int((deg - d) * 60)
        s = round((((deg - d) * 60) - m) * 60 * 100)
        return ((d, 1), (m, 1), (s, 100))

    exif = {
        "0th": {piexif.ImageIFD.DateTime: when},
        "Exif": {piexif.ExifIFD.DateTimeOriginal: when},
        "GPS": {
            piexif.GPSIFD.GPSLatitudeRef: "N" if lat >= 0 else "S",
            piexif.GPSIFD.GPSLatitude: dms(lat),
            piexif.GPSIFD.GPSLongitudeRef: "E" if lon >= 0 else "W",
            piexif.GPSIFD.GPSLongitude: dms(lon),
        },
    }
    img.save(path, "JPEG", exif=piexif.dump(exif))


@pytest.mark.unit
def test_read_metadata_extracts_gps_and_time(tmp_path: Path):
    p = tmp_path / "shot.jpg"
    _write_jpeg_with_gps(p, 44.5251, -110.8382)
    meta = read_metadata(p)

    assert meta["gps"] is not None
    lat, lon = meta["gps"]
    assert lat == pytest.approx(44.5251, abs=1e-3)
    assert lon == pytest.approx(-110.8382, abs=1e-3)
    assert meta["taken_at"] == "2025-06-21T09:00:00"
    assert meta["width"] == 64 and meta["height"] == 48


@pytest.mark.unit
def test_read_metadata_handles_no_exif(tmp_path: Path):
    p = tmp_path / "plain.jpg"
    Image.new("RGB", (10, 10), (0, 0, 0)).save(p, "JPEG")
    meta = read_metadata(p)
    assert meta["gps"] is None
    assert meta["taken_at"] is None
    assert meta["width"] == 10
