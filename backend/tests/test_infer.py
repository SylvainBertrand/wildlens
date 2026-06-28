"""Tests for time-based location inference (pure logic, no network)."""
from __future__ import annotations

import pytest

from app.ingest import _infer_locations
from app.models import GeoPoint, Identification, Photo


def _p(pid, taken_at, loc=None):
    return Photo(
        id=pid, trip="t", filename=f"{pid}.jpg",
        image_url="", thumb_url="",
        taken_at=taken_at,
        location=GeoPoint(lat=loc[0], lon=loc[1]) if loc else None,
        identification=Identification(provider="none", subjects=[]),
    )


@pytest.mark.unit
def test_infer_copies_nearest_in_time():
    photos = [
        _p("a", "2026-06-20T10:30:00", (44.46, -110.83)),
        _p("b", "2026-06-20T10:34:00", None),               # no GPS, nearest = a
        _p("c", "2026-06-20T10:40:00", (44.47, -110.84)),
    ]
    n = _infer_locations(photos, None, None, window=1800)
    assert n == 1
    b = photos[1]
    assert b.location_inferred is True
    assert b.location.lat == pytest.approx(44.46)


@pytest.mark.unit
def test_infer_respects_window():
    photos = [
        _p("a", "2026-06-20T10:30:00", (44.46, -110.83)),
        _p("b", "2026-06-20T13:30:00", None),  # 3h later -> outside 30m window
    ]
    assert _infer_locations(photos, None, None, window=1800) == 0
    assert photos[1].location is None


@pytest.mark.unit
def test_infer_noop_without_any_located():
    photos = [_p("a", "2026-06-20T10:30:00", None)]
    assert _infer_locations(photos, None, None, window=1800) == 0
