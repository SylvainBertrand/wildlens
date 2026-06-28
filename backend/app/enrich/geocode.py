"""Reverse geocoding via OpenStreetMap Nominatim (free, no API key).

Turns GPS coordinates into a human place name and an ordered list of candidate
titles to look up on Wikipedia. Results are cached on disk and calls are
rate-limited to respect Nominatim's usage policy.
"""
from __future__ import annotations

import urllib.parse
from pathlib import Path

from .http_cache import JsonCache, RateLimiter, http_get_json

# Address keys ordered most-specific -> least-specific. Used both to pick a
# concise place name and to build Wikipedia lookup candidates.
_CANDIDATE_KEYS = [
    "tourism", "attraction", "natural", "peak", "volcano", "water", "bay",
    "river", "protected_area", "national_park", "leisure", "building",
    "neighbourhood", "suburb", "hamlet", "village", "town", "city",
    "municipality", "county", "state", "country",
]


class NominatimGeocoder:
    def __init__(self, cache_path: Path, min_interval: float = 1.1):
        self.cache = JsonCache(cache_path)
        self.limiter = RateLimiter(min_interval)

    def reverse(self, lat: float, lon: float) -> dict | None:
        """Return {place_name, detail, candidates:[...]} or None.

        Cached by coordinates rounded to ~11 m so nearby shots share a lookup.
        """
        key = f"{round(lat, 4)},{round(lon, 4)}"
        if key in self.cache:
            return self.cache.get(key)

        self.limiter.wait()
        params = urllib.parse.urlencode({
            "lat": f"{lat:.6f}", "lon": f"{lon:.6f}",
            "format": "jsonv2", "zoom": "14", "addressdetails": "1",
        })
        data = http_get_json(f"https://nominatim.openstreetmap.org/reverse?{params}")
        result = self._parse(data) if data else None
        # Cache even None (as null) to avoid hammering the API on repeat failures.
        self.cache.set(key, result)
        return result

    @staticmethod
    def _parse(data: dict) -> dict | None:
        address = data.get("address", {}) or {}
        name = (data.get("name") or "").strip()

        candidates: list[str] = []
        if name:
            candidates.append(name)
        for k in _CANDIDATE_KEYS:
            v = address.get(k)
            if v and v not in candidates:
                candidates.append(v)

        if not candidates:
            return None

        place_name = name or candidates[0]
        # A short human detail line: "<locality>, <state>".
        locality = (address.get("hamlet") or address.get("village") or
                    address.get("town") or address.get("city") or
                    address.get("county"))
        state = address.get("state")
        detail = ", ".join(x for x in (locality, state) if x and x != place_name)

        return {"place_name": place_name, "detail": detail, "candidates": candidates}

    def save(self) -> None:
        self.cache.save()
