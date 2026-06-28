"""Tests for video metadata parsing (pure logic, no ffmpeg needed)."""
from __future__ import annotations

import pytest

from app.video import _parse_creation_time, _parse_iso6709


@pytest.mark.unit
def test_parse_iso6709_android():
    assert _parse_iso6709("+44.4280-110.3700/") == pytest.approx((44.428, -110.37))


@pytest.mark.unit
def test_parse_iso6709_with_altitude():
    lat, lon = _parse_iso6709("+37.7749-122.4194+010.000/")
    assert lat == pytest.approx(37.7749)
    assert lon == pytest.approx(-122.4194)


@pytest.mark.unit
def test_parse_iso6709_none():
    assert _parse_iso6709("") is None
    assert _parse_iso6709("not coords") is None


@pytest.mark.unit
def test_parse_creation_time_iso_z():
    assert _parse_creation_time("2026-06-22T10:00:00.000000Z") == "2026-06-22T10:00:00"


@pytest.mark.unit
def test_parse_creation_time_invalid():
    assert _parse_creation_time("") is None
    assert _parse_creation_time("garbage") is None


@pytest.mark.unit
def test_needs_web_version():
    from app.video import needs_web_version
    # HEVC in mp4 -> needs transcode
    assert needs_web_version("x.mp4", {"vcodec": "hevc", "acodec": "aac"}) is True
    # H.264/AAC mp4 -> fine as-is
    assert needs_web_version("x.mp4", {"vcodec": "h264", "acodec": "aac"}) is False
    # mkv container (not web) -> transcode even with h264
    assert needs_web_version("x.mkv", {"vcodec": "h264", "acodec": "aac"}) is True
    # unknown codecs -> play original (don't transcode blindly)
    assert needs_web_version("x.mp4", {"vcodec": None, "acodec": None}) is False
