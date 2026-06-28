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
