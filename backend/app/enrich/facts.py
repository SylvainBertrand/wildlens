"""Fun facts from Wikipedia (free, no API key).

Two strategies:
- nearby_fact(lat, lon): Wikipedia *geosearch* — find the article whose
  coordinates are closest to the photo, then return its summary. This is far more
  relevant than guessing by place name (e.g. it finds "Grand Prismatic Spring"
  rather than the county).
- fact_for([labels]): title-based summary lookup, used for vision-identified
  subjects (e.g. "American bison").

All lookups are cached on disk, including negative results.
"""
from __future__ import annotations

import urllib.parse
from pathlib import Path

from .http_cache import JsonCache, http_get_json

_MAX_CHARS = 280


def _trim(text: str, max_chars: int = _MAX_CHARS) -> str:
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    dot = cut.rfind(". ")
    if dot >= 80:
        return cut[: dot + 1]
    return cut.rstrip() + "\u2026"


class WikipediaFacts:
    def __init__(self, cache_path: Path):
        self.cache = JsonCache(cache_path)
        # Separate geosearch cache lives alongside the summary cache file.
        self.geo_cache = JsonCache(cache_path.with_name("wiki_geo.json"))

    # ---- title-based summary ------------------------------------------------
    def _summary(self, title: str) -> dict | None:
        key = title.strip()
        if key in self.cache:
            return self.cache.get(key)
        slug = urllib.parse.quote(key.replace(" ", "_"), safe="")
        data = http_get_json(f"https://en.wikipedia.org/api/rest_v1/page/summary/{slug}")
        result = None
        if data and data.get("type") != "disambiguation":
            extract = (data.get("extract") or "").strip()
            if extract:
                result = {
                    "title": data.get("title", key),
                    "extract": extract,
                    "url": (data.get("content_urls", {}).get("desktop", {}) or {}).get("page"),
                }
        self.cache.set(key, result)
        return result

    def fact_for(self, candidates: list[str]) -> dict | None:
        """Return {label, fun_fact, url} for the first candidate with a summary."""
        for title in candidates:
            if not title:
                continue
            summary = self._summary(title)
            if summary:
                return {
                    "label": summary["title"],
                    "fun_fact": _trim(summary["extract"]),
                    "url": summary.get("url"),
                }
        return None

    # ---- coordinate-based (geosearch) --------------------------------------
    def _geosearch(self, lat: float, lon: float, radius: int, limit: int) -> list[dict]:
        key = f"{round(lat, 4)},{round(lon, 4)}"
        if key in self.geo_cache:
            return self.geo_cache.get(key) or []
        params = urllib.parse.urlencode({
            "action": "query", "list": "geosearch",
            "gscoord": f"{lat:.6f}|{lon:.6f}", "gsradius": str(radius),
            "gslimit": str(limit), "format": "json",
        })
        data = http_get_json(f"https://en.wikipedia.org/w/api.php?{params}")
        results = []
        if data:
            for g in data.get("query", {}).get("geosearch", []):
                results.append({"title": g.get("title"), "dist": g.get("dist")})
        self.geo_cache.set(key, results)
        return results

    def nearby_fact(self, lat: float, lon: float, radius: int = 10000,
                    limit: int = 8) -> dict | None:
        """Return {label, fun_fact, url, dist} for the nearest article with a summary."""
        for hit in self._geosearch(lat, lon, radius, limit):
            title = hit.get("title")
            if not title:
                continue
            summary = self._summary(title)
            if summary:
                return {
                    "label": summary["title"],
                    "fun_fact": _trim(summary["extract"]),
                    "url": summary.get("url"),
                    "dist": hit.get("dist"),
                }
        return None

    def save(self) -> None:
        self.cache.save()
        self.geo_cache.save()
