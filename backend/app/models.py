"""Pydantic schemas shared by the API."""
from __future__ import annotations

from pydantic import BaseModel


class GeoPoint(BaseModel):
    lat: float
    lon: float


class IdentifiedSubject(BaseModel):
    """A thing recognized in a photo (landmark, animal, plant...)."""
    kind: str            # "landmark" | "fauna" | "flora" | "scene" | "unknown"
    label: str           # human-readable name
    confidence: float    # 0..1
    fun_fact: str | None = None
    source: str | None = None   # which provider / dataset produced this


class Identification(BaseModel):
    provider: str
    subjects: list[IdentifiedSubject] = []


class Photo(BaseModel):
    id: str
    trip: str
    filename: str
    image_url: str
    thumb_url: str
    taken_at: str | None = None       # ISO 8601 if known
    location: GeoPoint | None = None
    place_name: str | None = None
    width: int | None = None
    height: int | None = None
    identification: Identification | None = None


class Trip(BaseModel):
    name: str
    photo_count: int
    located_count: int                   # how many photos have GPS
    bounds: dict | None = None        # {minLat,minLon,maxLat,maxLon}


class PhotosResponse(BaseModel):
    trips: list[Trip]
    photos: list[Photo]
