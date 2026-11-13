"""FastAPI application: the API under /api, and the exported web UI at /."""

import asyncio
import contextlib
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from athena import __version__
from athena.api import capabilities, system
from athena.config import Settings
from athena.logging_setup import setup_logging
from athena.platform.store import CapabilityStore


def create_app(
    settings: Settings | None = None, capability_store: CapabilityStore | None = None
) -> FastAPI:
    settings = settings or Settings()
    if settings.log_to_file:
        setup_logging(settings.data_dir)
    store = capability_store or CapabilityStore()

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Detect in the background so the server answers immediately; the first
        # GET /api/system/capabilities waits for it if it isn't done yet.
        task = asyncio.create_task(store.get())
        yield
        task.cancel()

    app = FastAPI(
        title="Athena",
        version=__version__,
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.capabilities = store
    app.include_router(system.router, prefix="/api")
    app.include_router(capabilities.router, prefix="/api")

    # Mounted last so /api routes win. In development the UI is served by `next dev`
    # instead, and this directory doesn't exist.
    if (settings.web_dir / "index.html").is_file():
        app.mount("/", StaticFiles(directory=settings.web_dir, html=True), name="web")
    else:

        @app.get("/", include_in_schema=False)
        def no_web_ui() -> JSONResponse:
            return JSONResponse(
                {
                    "detail": "Web UI not bundled. In development run `pnpm dev` and open "
                    "http://localhost:3000; the API docs are at /api/docs."
                }
            )

    return app
