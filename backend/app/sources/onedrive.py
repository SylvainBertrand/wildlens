"""Microsoft OneDrive (Graph) client using the OAuth device-code flow.

Device-code flow is ideal for a headless LAN host: the user opens a URL on any
device, types a short code, and consents — no redirect server, no client secret.

Only `urllib` is used (no new deps), and this module is imported lazily by the
API router so it never weighs on the idle server. The refresh token is stored in
gitignored `data/` (never the public repo).
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from ..config import settings

SCOPES = "Files.Read offline_access User.Read"
GRAPH = "https://graph.microsoft.com/v1.0"
GRAPH_PREFIX = "https://graph.microsoft.com/"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".tif", ".tiff"}
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm", ".3gp", ".mts", ".hevc"}

# In-memory access-token cache (avoids refreshing on every request).
_access_cache: dict = {"token": None, "expires_at": 0.0}


def _auth_base() -> str:
    return f"https://login.microsoftonline.com/{settings.onedrive_tenant}/oauth2/v2.0"


class OneDriveError(RuntimeError):
    pass


class NotConnectedError(OneDriveError):
    pass


def _post_form(url: str, fields: dict, timeout: float = 30.0) -> tuple[int, dict]:
    body = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read().decode())
        except (ValueError, OSError):
            return exc.code, {"error": "http_error", "error_description": str(exc)}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise OneDriveError(f"network error: {exc}") from exc


def _graph_get(path_or_url: str, token: str, timeout: float = 30.0, raw: bool = False):
    url = path_or_url if path_or_url.startswith("http") else f"{GRAPH}{path_or_url}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            return data if raw else json.loads(data.decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise OneDriveError(f"Graph {exc.code}: {detail[:200]}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise OneDriveError(f"network error: {exc}") from exc


# --- token storage ---------------------------------------------------------
def _load_token_file() -> dict | None:
    p = settings.onedrive_token_path
    if p.exists():
        try:
            return json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            return None
    return None


def _save_token_file(refresh_token: str, account: dict | None) -> None:
    settings.onedrive_token_path.parent.mkdir(parents=True, exist_ok=True)
    settings.onedrive_token_path.write_text(json.dumps(
        {"refresh_token": refresh_token, "account": account, "saved_at": time.time()},
        indent=2))


def is_connected() -> bool:
    return _load_token_file() is not None


def disconnect() -> None:
    _access_cache.update(token=None, expires_at=0.0)
    settings.onedrive_token_path.unlink(missing_ok=True)


# --- device-code auth ------------------------------------------------------
def start_device_code() -> dict:
    if not settings.onedrive_configured:
        raise OneDriveError("OneDrive is not configured (set WILDLENS_ONEDRIVE_CLIENT_ID)")
    status, data = _post_form(f"{_auth_base()}/devicecode", {
        "client_id": settings.onedrive_client_id,
        "scope": SCOPES,
    })
    if status != 200 or "device_code" not in data:
        raise OneDriveError(data.get("error_description", "failed to start device code"))
    return data  # device_code, user_code, verification_uri, expires_in, interval, message


def poll_for_token(device_code: str) -> str:
    """Poll the token endpoint once. Returns: 'pending' | 'connected' | error string."""
    status, data = _post_form(f"{_auth_base()}/token", {
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        "client_id": settings.onedrive_client_id,
        "device_code": device_code,
    })
    if status == 200 and "access_token" in data:
        _access_cache.update(token=data["access_token"],
                             expires_at=time.time() + int(data.get("expires_in", 3600)) - 60)
        account = None
        try:
            me = _graph_get("/me", data["access_token"])
            account = {"name": me.get("displayName"),
                       "email": me.get("userPrincipalName") or me.get("mail")}
        except OneDriveError:
            pass
        _save_token_file(data.get("refresh_token", ""), account)
        return "connected"
    err = data.get("error", "unknown_error")
    if err in ("authorization_pending", "slow_down"):
        return "pending"
    return data.get("error_description", err)


# --- access token ----------------------------------------------------------
def get_access_token() -> str:
    if _access_cache["token"] and _access_cache["expires_at"] > time.time():
        return _access_cache["token"]
    tok = _load_token_file()
    if not tok or not tok.get("refresh_token"):
        raise NotConnectedError("OneDrive not connected")
    status, data = _post_form(f"{_auth_base()}/token", {
        "grant_type": "refresh_token",
        "client_id": settings.onedrive_client_id,
        "refresh_token": tok["refresh_token"],
        "scope": SCOPES,
    })
    if status != 200 or "access_token" not in data:
        raise NotConnectedError(data.get("error_description", "token refresh failed"))
    _access_cache.update(token=data["access_token"],
                         expires_at=time.time() + int(data.get("expires_in", 3600)) - 60)
    if data.get("refresh_token"):
        _save_token_file(data["refresh_token"], (tok or {}).get("account"))
    return _access_cache["token"]


def account_info() -> dict | None:
    tok = _load_token_file()
    return (tok or {}).get("account") if tok else None


# --- browse / download -----------------------------------------------------
def _classify(item: dict) -> str | None:
    if "folder" in item:
        return "folder"
    name = item.get("name", "")
    ext = Path(name).suffix.lower()
    mime = (item.get("file") or {}).get("mimeType", "")
    if mime.startswith("image/") or ext in IMAGE_EXTS:
        return "image"
    if mime.startswith("video/") or "video" in item or ext in VIDEO_EXTS:
        return "video"
    return None


def _media_entry(item: dict, kind: str) -> dict:
    thumb_url = None
    thumbs = item.get("thumbnails") or []
    if thumbs:
        thumb_url = (thumbs[0].get("medium") or thumbs[0].get("large")
                     or thumbs[0].get("small") or {}).get("url")
    entry = {"id": item["id"], "name": item["name"], "size": item.get("size"),
             "media_type": kind, "thumb_url": thumb_url}
    if kind == "video":
        entry["duration"] = (item.get("video") or {}).get("duration")  # ms
    return entry


def _list_folders(item_id: str | None, token: str) -> list[dict]:
    """Subfolders only (filtered), so they always show regardless of media paging."""
    base = (f"/me/drive/items/{item_id}/children" if item_id
            else "/me/drive/root/children")
    url = base + "?$filter=folder%20ne%20null&$top=200&$select=id,name,folder"
    folders: list[dict] = []
    while url:
        data = _graph_get(url, token)
        for item in data.get("value", []):
            folders.append({"id": item["id"], "name": item["name"],
                            "count": (item.get("folder") or {}).get("childCount", 0)})
        url = data.get("@odata.nextLink")
    folders.sort(key=lambda f: f["name"].lower())
    return folders


def browse(item_id: str | None = None, cursor: str | None = None,
           page_size: int = 60) -> dict:
    """Page through a OneDrive folder's media, newest first.

    Returns {folders, media, next}. `folders` is populated only on the first
    page (cursor=None). `media` holds images + videos for this page with inline
    thumbnail URLs. `next` is an opaque cursor for the following page (or None).
    """
    token = get_access_token()

    if cursor:
        # SSRF guard: only ever follow Graph-issued continuation URLs.
        if not cursor.startswith(GRAPH_PREFIX):
            raise OneDriveError("invalid cursor")
        data = _graph_get(cursor, token)
        folders = []
    else:
        base = (f"/me/drive/items/{item_id}/children" if item_id
                else "/me/drive/root/children")
        query = (f"?$top={int(page_size)}&$orderby=lastModifiedDateTime%20desc"
                 "&$expand=thumbnails&$select=id,name,folder,file,size,video")
        data = _graph_get(base + query, token)
        folders = _list_folders(item_id, token)

    media: list[dict] = []
    for item in data.get("value", []):
        kind = _classify(item)
        if kind in ("image", "video"):
            media.append(_media_entry(item, kind))

    return {"folders": folders, "media": media, "next": data.get("@odata.nextLink")}


def thumbnail_bytes(item_id: str) -> bytes:
    token = get_access_token()
    meta = _graph_get(f"/me/drive/items/{item_id}/thumbnails/0/medium", token)
    url = meta.get("url")
    if not url:
        raise OneDriveError("no thumbnail available")
    return _graph_get(url, token, raw=True)


def get_item_download(item_id: str) -> tuple[str, str]:
    """Return (filename, pre-authenticated download URL) for a OneDrive item.

    The @microsoft.graph.downloadUrl is short-lived and already authenticated, so
    it must be fetched WITHOUT an Authorization header (sending the bearer token
    to it yields 401).
    """
    token = get_access_token()
    meta = _graph_get(f"/me/drive/items/{item_id}", token)
    name = meta.get("name", f"{item_id}.bin")
    url = meta.get("@microsoft.graph.downloadUrl") or meta.get("@content.downloadUrl")
    if not url:
        raise OneDriveError("no download URL for item")
    return name, url


def stream_to(url: str, dest, timeout: float = 300.0) -> None:
    """Stream a pre-authenticated download URL to a file (no auth header)."""
    import shutil
    req = urllib.request.Request(url)  # deliberately no Authorization header
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp, open(dest, "wb") as fh:
            shutil.copyfileobj(resp, fh, length=1024 * 256)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        raise OneDriveError(f"download failed: {exc}") from exc
