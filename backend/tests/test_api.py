"""Smoke tests for the API and the mock identification provider."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.identification import get_provider
from app.main import create_app


@pytest.mark.unit
def test_health_endpoint():
    client = TestClient(create_app())
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.unit
def test_mock_provider_is_deterministic():
    provider = get_provider("mock")
    a = provider.identify("/photos/trip/bison.jpg")
    b = provider.identify("/photos/trip/bison.jpg")
    assert a.provider == "mock"
    assert len(a.subjects) >= 1
    # Same input -> same identification (seeded by path).
    assert [s.label for s in a.subjects] == [s.label for s in b.subjects]
    # Every subject carries a fun fact and a confidence in [0, 1].
    for s in a.subjects:
        assert s.fun_fact
        assert 0.0 <= s.confidence <= 1.0
