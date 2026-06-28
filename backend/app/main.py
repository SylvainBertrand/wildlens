"""wildlens FastAPI application factory.

The runtime server is intentionally minimal: it only reads the precomputed index
and serves files. No Pillow / network / ML is imported here, so idle memory is
small. Combined with systemd socket activation + idle auto-shutdown (see
WILDLENS_IDLE_TIMEOUT and deploy/), the process uses ~zero CPU/RAM when unused.
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import time
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import REPO_ROOT, settings
from .routers import manage, photos


class _Activity:
    """Tracks the time of the last request for idle auto-shutdown."""

    def __init__(self) -> None:
        self.last = time.monotonic()

    def touch(self) -> None:
        self.last = time.monotonic()


async def _idle_watchdog(activity: _Activity, timeout: int) -> None:
    """Exit the process after `timeout` seconds of inactivity.

    Under systemd socket activation the socket stays listening, so the next
    request transparently restarts the service. This is what keeps idle
    CPU/RAM at zero without dropping requests.
    """
    check = max(5, min(timeout, 30))
    try:
        while True:
            await asyncio.sleep(check)
            if time.monotonic() - activity.last >= timeout:
                # Graceful shutdown: uvicorn handles SIGTERM cleanly.
                signal.raise_signal(signal.SIGTERM)
                return
    except asyncio.CancelledError:
        pass


def create_app() -> FastAPI:
    activity = _Activity()
    idle_timeout = settings.idle_timeout

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        task = None
        if idle_timeout and idle_timeout > 0:
            task = asyncio.create_task(_idle_watchdog(activity, idle_timeout))
        try:
            yield
        finally:
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    app = FastAPI(title="wildlens", version="0.2.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if idle_timeout and idle_timeout > 0:
        @app.middleware("http")
        async def _track_activity(request: Request, call_next):
            activity.touch()
            return await call_next(request)

    app.include_router(photos.router)
    app.include_router(manage.router)

    @app.get("/api/health")
    def health() -> dict:
        return {
            "status": "ok",
            "id_provider": settings.id_provider,
            "idle_timeout": idle_timeout,
        }

    # In production, serve the built frontend from the same origin so one process
    # serves both API and UI. Build: cd frontend && npm run build
    dist = REPO_ROOT / "frontend" / "dist"
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="frontend")

    return app


app = create_app()


def run() -> None:
    import uvicorn

    # Socket activation: if systemd passed a listening socket (LISTEN_FDS), bind
    # to fd 3 instead of host/port so restarts never drop connections.
    if os.environ.get("LISTEN_FDS"):
        uvicorn.run("app.main:app", fd=3, log_level="info")
    else:
        uvicorn.run("app.main:app", host=settings.host, port=settings.port, log_level="info")


if __name__ == "__main__":
    run()
