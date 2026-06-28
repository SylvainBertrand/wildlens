"""Tests for perceptual-hash dedup (pure logic)."""
from __future__ import annotations

import pytest

from app.dedup import cluster, hamming


@pytest.mark.unit
def test_hamming():
    assert hamming("0000000000000000", "0000000000000000") == 0
    assert hamming("0000000000000000", "0000000000000001") == 1
    assert hamming("00000000000000ff", "0000000000000000") == 8


@pytest.mark.unit
def test_cluster_groups_near_duplicates():
    items = [
        {"id": "a", "trip": "t", "dhash": "ffffffffffffffff", "ts": 0},
        {"id": "b", "trip": "t", "dhash": "fffffffffffffffe", "ts": 10},   # 1 bit off
        {"id": "c", "trip": "t", "dhash": "0000000000000000", "ts": 20},   # far
    ]
    groups = cluster(items, threshold=10, time_window=180)
    assert groups.get("a") == groups.get("b")          # a,b grouped
    assert groups.get("a") is not None
    assert "c" not in groups                            # c is unique


@pytest.mark.unit
def test_cluster_respects_time_window():
    items = [
        {"id": "a", "trip": "t", "dhash": "ffffffffffffffff", "ts": 0},
        {"id": "b", "trip": "t", "dhash": "ffffffffffffffff", "ts": 10_000},  # same look, far in time
    ]
    assert cluster(items, threshold=10, time_window=180) == {}


@pytest.mark.unit
def test_cluster_separates_trips():
    items = [
        {"id": "a", "trip": "t1", "dhash": "ffffffffffffffff", "ts": 0},
        {"id": "b", "trip": "t2", "dhash": "ffffffffffffffff", "ts": 5},
    ]
    assert cluster(items, threshold=10, time_window=180) == {}
