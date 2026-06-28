"""Provider registry: map a config key to an identification provider instance."""
from __future__ import annotations

from functools import cache

from .base import IdentificationProvider
from .mock import MockProvider


@cache
def get_provider(name: str = "mock") -> IdentificationProvider:
    name = (name or "mock").lower()
    if name == "mock":
        return MockProvider()
    # Future: "clip", "wikipedia", "claude", "openai"...
    raise ValueError(f"Unknown identification provider: {name!r}")
