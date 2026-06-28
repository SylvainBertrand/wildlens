"""Application configuration (env-overridable)."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root = two levels up from this file (backend/app/config.py -> repo root)
REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WILDLENS_", env_file=".env", extra="ignore")

    # Where photos live (gitignored). Organize as data/photos/<trip>/...
    data_dir: Path = REPO_ROOT / "data"

    # Server binding. 0.0.0.0 makes it reachable on the LAN (e.g. from shumai).
    host: str = "0.0.0.0"
    port: int = 8000

    # Identification provider key. "none" (default): no image-based ID, but
    # photos still get place names + Wikipedia facts via the ingest pipeline.
    # "mock": demo subjects. "claude": real vision via the Claude CLI (opt-in).
    id_provider: str = "none"

    # Ingest-time enrichment (network, cached). Disable for fully offline ingest.
    geocode_enabled: bool = True   # GPS -> place name (Nominatim)
    facts_enabled: bool = True     # place/subject -> fun fact (Wikipedia)

    # Near-duplicate grouping (perceptual hash, ingest-time). Higher threshold =
    # looser grouping. time_window bounds grouping to photos taken close together.
    dedup_enabled: bool = True
    dedup_threshold: int = 14      # max Hamming distance (0-64) to group
    dedup_time_window: int = 300   # seconds

    # Infer a location for media missing GPS from the nearest-in-time photo in
    # the same trip (within infer_location_window seconds). Marked as inferred.
    infer_location_enabled: bool = True
    infer_location_window: int = 1800  # seconds (30 min)

    # Idle auto-shutdown (seconds). >0 makes the server exit after this much
    # inactivity so socket activation can keep idle CPU/RAM at zero. 0 disables
    # (always-on). Intended to be set by the socket-activated systemd unit.
    idle_timeout: int = 0

    # Thumbnail max edge in px.
    thumb_size: int = 480

    # CORS origins allowed for the frontend dev server.
    cors_origins: list[str] = ["*"]

    # --- OneDrive import source (optional). Empty client id => feature hidden. ---
    onedrive_client_id: str = ""
    # Authority tenant: "consumers" (personal MS accounts), "common", or a tenant id.
    onedrive_tenant: str = "consumers"

    @property
    def photos_dir(self) -> Path:
        return self.data_dir / "photos"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def thumbs_dir(self) -> Path:
        return self.cache_dir / "thumbs"

    @property
    def web_dir(self) -> Path:
        # Browser-friendly transcoded video versions (for HEVC etc.).
        return self.cache_dir / "web"

    @property
    def index_path(self) -> Path:
        return self.cache_dir / "index.json"

    @property
    def geocode_cache_path(self) -> Path:
        return self.cache_dir / "geocode.json"

    @property
    def facts_cache_path(self) -> Path:
        return self.cache_dir / "facts.json"

    @property
    def enrich_cache_path(self) -> Path:
        return self.cache_dir / "enrich.json"

    @property
    def onedrive_token_path(self) -> Path:
        # Holds the OAuth refresh token — lives in gitignored data/, never the repo.
        return self.data_dir / "onedrive_token.json"

    @property
    def trash_dir(self) -> Path:
        # Deleted originals are moved here (recoverable). Not scanned by ingest.
        return self.data_dir / ".trash"

    @property
    def onedrive_configured(self) -> bool:
        return bool(self.onedrive_client_id)


settings = Settings()
