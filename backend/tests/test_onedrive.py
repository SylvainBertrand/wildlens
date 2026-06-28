"""Tests for OneDrive source helpers and unconfigured API behavior."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_app
from app.sources import onedrive


@pytest.mark.unit
def test_classify_folder_image_other():
    assert onedrive._classify({"folder": {"childCount": 3}, "name": "Trips"}) == "folder"
    assert onedrive._classify({"name": "a.JPG", "file": {"mimeType": "image/jpeg"}}) == "image"
    assert onedrive._classify({"name": "x.heic"}) == "image"
    assert onedrive._classify({"name": "notes.txt", "file": {"mimeType": "text/plain"}}) is None


@pytest.mark.unit
def test_status_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "onedrive_client_id", "")
    client = TestClient(create_app())
    r = client.get("/api/sources/onedrive/status")
    assert r.status_code == 200
    assert r.json() == {"configured": False, "connected": False}


@pytest.mark.unit
def test_connect_requires_configuration(monkeypatch):
    monkeypatch.setattr(settings, "onedrive_client_id", "")
    client = TestClient(create_app())
    assert client.post("/api/sources/onedrive/connect").status_code == 400
    assert client.get("/api/sources/onedrive/browse").status_code == 400


@pytest.mark.unit
def test_is_connected_reads_token_file(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    assert onedrive.is_connected() is False
    (tmp_path).mkdir(exist_ok=True)
    settings.onedrive_token_path.write_text('{"refresh_token": "x"}')
    assert onedrive.is_connected() is True
