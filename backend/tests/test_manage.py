"""Tests for management endpoints (upload, ingest trigger, status) and helpers."""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import settings
from app.main import create_app
from app.routers.manage import _safe_filename, _slug, _unique_path


@pytest.mark.unit
def test_slug_sanitizes():
    assert _slug("Yellowstone 2025!", "x") == "yellowstone-2025"
    assert _slug("../../etc", "x") == "etc"
    assert _slug("   ", "fallback") == "fallback"


@pytest.mark.unit
def test_safe_filename_strips_paths():
    assert _safe_filename("/etc/passwd") == "passwd"
    assert _safe_filename("../../x.JPG").endswith(".jpg")
    assert "/" not in _safe_filename("a/b/c.png")


@pytest.mark.unit
def test_unique_path_avoids_collision(tmp_path):
    (tmp_path / "a.jpg").write_text("x")
    p = _unique_path(tmp_path, "a.jpg")
    assert p.name == "a-1.jpg"


def _jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), (10, 20, 30)).save(buf, "JPEG")
    return buf.getvalue()


@pytest.mark.unit
def test_upload_rejects_non_image(monkeypatch, tmp_path):
    # Redirect data dir so the test never touches real photos, and stub the
    # ingest trigger so no subprocess is spawned.
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr("app.routers.manage.request_ingest", lambda: None)
    client = TestClient(create_app())

    r = client.post("/api/upload", files={"files": ("notes.txt", b"hello", "text/plain")})
    assert r.status_code == 400


@pytest.mark.unit
def test_upload_saves_image_and_triggers(monkeypatch, tmp_path):
    triggered = {"n": 0}
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr("app.routers.manage.request_ingest",
                        lambda: triggered.__setitem__("n", triggered["n"] + 1))
    client = TestClient(create_app())

    r = client.post(
        "/api/upload",
        data={"trip": "My Trip"},
        files={"files": ("shot.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["trip"] == "my-trip"
    assert body["saved"] == ["my-trip/shot.jpg"]
    assert triggered["n"] == 1
    assert (tmp_path / "photos" / "my-trip" / "shot.jpg").exists()
