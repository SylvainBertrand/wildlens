"""Ingest-time enrichment (geocoding, fun facts).

These modules make network calls and are imported ONLY by the ingest pipeline,
never by the runtime server — so the idle server stays tiny and dependency-free.
"""
