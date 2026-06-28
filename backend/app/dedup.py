"""Near-duplicate detection via perceptual hashing (ingest-time only).

A difference hash (dHash) is computed per image with Pillow (no extra deps).
Visually similar images have a small Hamming distance. Photos are then clustered
within a trip using both perceptual similarity AND temporal proximity, so bursts
and slight variations of the same scene group together without lumping in
unrelated look-alikes.
"""
from __future__ import annotations

from PIL import Image, ImageOps

HASH_SIZE = 8  # -> 64-bit hash


def dhash(path, size: int = HASH_SIZE) -> str | None:
    """Return a hex difference-hash for an image, or None on failure."""
    try:
        with Image.open(path) as img:
            img = ImageOps.exif_transpose(img).convert("L").resize(
                (size + 1, size), Image.BILINEAR)
            px = list(img.getdata())
    except Exception:  # noqa: BLE001
        return None
    width = size + 1
    bits = 0
    for row in range(size):
        base = row * width
        for col in range(size):
            bits = (bits << 1) | (1 if px[base + col] > px[base + col + 1] else 0)
    return f"{bits:016x}"


def hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


class _UnionFind:
    def __init__(self):
        self.parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.parent.setdefault(x, x)
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def cluster(items: list[dict], threshold: int = 10, time_window: int = 180,
            pos_window: int = 40) -> dict[str, str]:
    """Cluster near-duplicate images. Returns {photo_id: group_id} for grouped
    photos only (singletons are omitted).

    items: list of {id, trip, dhash, ts} where ts is epoch seconds or None.
    Photos are compared within the same trip, ordered by time, against recent
    neighbours bounded by `time_window` seconds (and `pos_window` positions when
    timestamps are missing).
    """
    uf = _UnionFind()
    by_trip: dict[str, list[dict]] = {}
    for it in items:
        if it.get("dhash"):
            by_trip.setdefault(it["trip"], []).append(it)

    for trip_items in by_trip.values():
        ordered = sorted(trip_items, key=lambda x: (x["ts"] is None, x["ts"] or 0, x["id"]))
        for i, a in enumerate(ordered):
            for j in range(i - 1, max(-1, i - pos_window - 1), -1):
                b = ordered[j]
                if a["ts"] is not None and b["ts"] is not None:
                    if a["ts"] - b["ts"] > time_window:
                        break  # ordered by time; older ones are even further
                if hamming(a["dhash"], b["dhash"]) <= threshold:
                    uf.union(a["id"], b["id"])

    # Collect cluster sizes; assign group ids only to clusters with >1 member.
    members: dict[str, list[str]] = {}
    for it in items:
        if it.get("dhash"):
            members.setdefault(uf.find(it["id"]), []).append(it["id"])

    groups: dict[str, str] = {}
    for root, ids in members.items():
        if len(ids) > 1:
            for pid in ids:
                groups[pid] = f"g_{root}"
    return groups
