"""wildlens FastAPI application factory."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import REPO_ROOT, settings
from .routers import photos


def create_app() -> FastAPI:
    """Build and configure the FastAPI app.

    Factory pattern (mirrors trading_company's src/app.py) so tests and
    socket-activated servers can construct fresh instances cleanly.
    """
    app = FastAPI(title="wildlens", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(photos.router)

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "id_provider": settings.id_provider}

    # In production (e.g. on shumai), serve the built frontend from the same
    # origin so one process serves both API and UI. Build: cd frontend && npm run build
    dist = REPO_ROOT / "frontend" / "dist"
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="frontend")

    return app


# Module-level app for `uvicorn app.main:app`.
app = create_app()


def run() -> None:
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    run()
