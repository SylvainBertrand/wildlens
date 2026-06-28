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

    # Identification provider key: "mock" for now. Later: "clip", "claude", "wikipedia"...
    id_provider: str = "mock"

    # Thumbnail max edge in px.
    thumb_size: int = 480

    # CORS origins allowed for the frontend dev server.
    cors_origins: list[str] = ["*"]

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
    def index_path(self) -> Path:
        return self.cache_dir / "index.json"


settings = Settings()
