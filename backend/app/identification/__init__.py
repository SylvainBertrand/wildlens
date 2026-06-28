"""Pluggable identification providers.

Swap real AI in later by adding a provider and registering it, without
touching the API or ingest code.
"""
from .registry import get_provider

__all__ = ["get_provider"]
