"""Provider interface for photo identification."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..models import Identification


@runtime_checkable
class IdentificationProvider(Protocol):
    name: str

    def identify(self, image_path: str, context: dict | None = None) -> Identification:
        """Analyze an image and return identified subjects + fun facts.

        `context` may include hints such as {"place_name": ..., "lat":..., "lon":...}.
        Implementations must be safe to call offline (return empty subjects on failure).
        """
        ...
