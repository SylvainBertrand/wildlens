"""Video metadata + poster extraction via ffmpeg/ffprobe (ingest-time only).

Imported lazily by the ingest pipeline, so the runtime server never depends on
ffmpeg. Everything degrades gracefully if ffmpeg/ffprobe aren't installed:
metadata returns blanks and poster generation is skipped (UI shows a placeholder).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

_ISO6709 = re.compile(r"([+-]\d+(?:\.\d+)?)([+-]\d+(?:\.\d+)?)")


def _resolve(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    local = Path(os.path.expanduser("~/.local/bin")) / name
    return str(local) if local.exists() else None


def ffmpeg_bin() -> str | None:
    return _resolve("ffmpeg")


def ffprobe_bin() -> str | None:
    return _resolve("ffprobe")


def _parse_iso6709(value: str) -> tuple[float, float] | None:
    """Parse '+44.4280-110.3700/' style location strings -> (lat, lon)."""
    if not value:
        return None
    m = _ISO6709.search(value)
    if not m:
        return None
    try:
        return float(m.group(1)), float(m.group(2))
    except ValueError:
        return None


def _parse_creation_time(value: str) -> str | None:
    if not value:
        return None
    v = value.strip().replace("Z", "+00:00")
    for fmt in (None,):  # try fromisoformat first
        try:
            dt = datetime.fromisoformat(v)
            return dt.replace(tzinfo=None).isoformat()
        except ValueError:
            break
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(value.strip(), fmt)
            return dt.replace(tzinfo=None).isoformat()
        except ValueError:
            continue
    return None


def read_metadata(path) -> dict:
    """Return {gps, taken_at, duration, width, height} for a video via ffprobe."""
    out: dict = {"gps": None, "taken_at": None, "duration": None,
                 "width": None, "height": None}
    probe = ffprobe_bin()
    if not probe:
        return out
    try:
        proc = subprocess.run(
            [probe, "-v", "quiet", "-print_format", "json",
             "-show_format", "-show_streams", str(path)],
            capture_output=True, text=True, timeout=60,
        )
        data = json.loads(proc.stdout or "{}")
    except (subprocess.TimeoutExpired, OSError, ValueError):
        return out

    fmt = data.get("format", {})
    tags = {k.lower(): v for k, v in (fmt.get("tags") or {}).items()}

    try:
        out["duration"] = round(float(fmt.get("duration")), 2) if fmt.get("duration") else None
    except (TypeError, ValueError):
        pass

    for key in ("com.apple.quicktime.location.iso6709", "location", "location-eng"):
        if key in tags:
            gps = _parse_iso6709(tags[key])
            if gps:
                out["gps"] = gps
                break

    for key in ("creation_time", "com.apple.quicktime.creationdate", "date"):
        if key in tags:
            ts = _parse_creation_time(tags[key])
            if ts:
                out["taken_at"] = ts
                break

    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            out["width"] = stream.get("width")
            out["height"] = stream.get("height")
            if not out["taken_at"]:
                stags = {k.lower(): v for k, v in (stream.get("tags") or {}).items()}
                if "creation_time" in stags:
                    out["taken_at"] = _parse_creation_time(stags["creation_time"])
            break
    return out


def make_poster(src, dest, size: int) -> bool:
    """Write a JPEG poster frame for the video; returns True on success."""
    ff = ffmpeg_bin()
    if not ff:
        return False
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    vf = f"scale={size}:{size}:force_original_aspect_ratio=decrease"
    for seek in ("1", "0"):  # 1s in (avoid black frame), fall back to first frame
        try:
            proc = subprocess.run(
                [ff, "-y", "-ss", seek, "-i", str(src), "-frames:v", "1",
                 "-vf", vf, "-q:v", "3", str(dest)],
                capture_output=True, timeout=120,
            )
        except (subprocess.TimeoutExpired, OSError):
            return False
        if proc.returncode == 0 and dest.exists() and dest.stat().st_size > 0:
            return True
    return False
