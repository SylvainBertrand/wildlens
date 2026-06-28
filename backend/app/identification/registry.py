"""Provider registry: map a config key to an identification provider instance."""
from __future__ import annotations

from functools import cache

from .base import IdentificationProvider


@cache
def get_provider(name: str = "none") -> IdentificationProvider:
    name = (name or "none").lower()
    if name in ("none", "geo", "off"):
        from .none_provider import NoneProvider
        return NoneProvider()
    if name == "mock":
        from .mock import MockProvider
        return MockProvider()
    if name == "claude":
        from .claude import ClaudeCLIProvider
        return ClaudeCLIProvider()
    # Future: "clip", ...
    raise ValueError(f"Unknown identification provider: {name!r}")
