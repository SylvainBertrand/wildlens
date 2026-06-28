"""No-vision provider.

Returns no image-based subjects. With this default provider, photos still get a
real place name + Wikipedia fun fact from the ingest pipeline's geocoding step —
no API keys, no ML, nothing heavy. Image-based ID is opt-in (see claude.py).
"""
from __future__ import annotations

from ..models import Identification


class NoneProvider:
    name = "none"

    def identify(self, image_path: str, context: dict | None = None) -> Identification:
        return Identification(provider=self.name, subjects=[])
