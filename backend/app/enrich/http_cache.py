"""Tiny persistent JSON cache + a polite HTTP GET helper (stdlib only).

Used by the enrichment modules so re-ingesting photos doesn't re-hit the network.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

USER_AGENT = "wildlens/0.2 (https://github.com/SylvainBertrand/wildlens)"


class JsonCache:
    """Dict-like cache persisted to a JSON file. Single-process (ingest) use."""

    def __init__(self, path: Path):
        self.path = path
        self._data: dict = {}
        if path.exists():
            try:
                self._data = json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def set(self, key: str, value) -> None:
        self._data[key] = value

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(self._data, indent=2, ensure_ascii=False))
        tmp.replace(self.path)


def http_get_json(url: str, timeout: float = 15.0) -> dict | None:
    """GET a URL and parse JSON. Returns None on any network/parse error."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, OSError):
        return None


class RateLimiter:
    """Enforce a minimum interval between calls (e.g. Nominatim's 1 req/s policy)."""

    def __init__(self, min_interval: float):
        self.min_interval = min_interval
        self._last = 0.0

    def wait(self) -> None:
        elapsed = time.monotonic() - self._last
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last = time.monotonic()
