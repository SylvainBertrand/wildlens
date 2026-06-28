"""Unit tests for enrichment pure-logic (no network) and the none provider."""
from __future__ import annotations

import pytest

from app.enrich.facts import _trim
from app.enrich.geocode import NominatimGeocoder
from app.identification import get_provider


@pytest.mark.unit
def test_trim_keeps_short_text():
    assert _trim("Short fact.") == "Short fact."


@pytest.mark.unit
def test_trim_cuts_long_text_on_sentence_boundary():
    text = "First sentence is reasonably long and informative. " + "x" * 400
    out = _trim(text)
    assert len(out) <= 281
    assert out.endswith(".") or out.endswith("\u2026")


@pytest.mark.unit
def test_geocode_parse_builds_place_and_candidates():
    data = {
        "name": "Old Faithful",
        "address": {
            "tourism": "Old Faithful",
            "county": "Teton County",
            "state": "Wyoming",
            "country": "United States",
        },
    }
    parsed = NominatimGeocoder._parse(data)
    assert parsed is not None
    assert parsed["place_name"] == "Old Faithful"
    assert "Old Faithful" in parsed["candidates"]
    assert "Wyoming" in parsed["candidates"]
    # Detail line excludes the place name itself.
    assert "Old Faithful" not in parsed["detail"]


@pytest.mark.unit
def test_geocode_parse_returns_none_when_empty():
    assert NominatimGeocoder._parse({"address": {}}) is None


@pytest.mark.unit
def test_none_provider_yields_no_subjects():
    ident = get_provider("none").identify("/photos/x.jpg")
    assert ident.provider == "none"
    assert ident.subjects == []
