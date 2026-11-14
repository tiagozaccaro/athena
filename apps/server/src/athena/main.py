"""FastAPI application: the API under /api, and the exported web UI at /."""

import asyncio
import contextlib
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from athena import __version__
from athena.api import apps, auth, capabilities, containers, jobs, system
from athena.api import settings as settings_api
from athena.api import store as store_api
from athena.auth.deps import require_user
from athena.auth.service import LoginThrottle
from athena.catalog.registry import CatalogRegistry
from athena.config import Settings
from athena.db import Database
from athena.jobs import JobManager
from athena.logging_setup import setup_logging
from athena.monitor import HostMonitor
from athena.platform.store import CapabilityStore


def create_app(
    settings: Settings | None = None,
    capability_store: CapabilityStore | None = None,
    catalogs: CatalogRegistry | None = None,
    monitor: HostMonitor | None = None,
) -> FastAPI:
    settings = settings or Settings()
    if settings.log_to_file:
        setup_logging(settings.data_dir)
    store = capability_store or CapabilityStore()
    db = Database(settings.data_dir / "athena.db")
    db.migrate()

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Detect in the background so the server answers immediately; the first
        # GET /api/system/capabilities waits for it if it isn't done yet.
        task = asyncio.create_task(store.get())
        app.state.monitor.start()
        yield
        task.cancel()
        await app.state.monitor.stop()

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
    app.state.db = db
    app.state.login_throttle = LoginThrottle()
    app.state.jobs = JobManager()
    app.state.app_jobs = {}
    app.state.monitor = monitor or HostMonitor()
    app.state.catalogs = catalogs or CatalogRegistry(remote_root=settings.data_dir / "catalogs")
    # Public: /api/health and /api/auth/*. Everything else needs a signed-in session.
    app.include_router(system.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(capabilities.router, prefix="/api", dependencies=[require_user])
    app.include_router(jobs.router, prefix="/api", dependencies=[require_user])
    # The runtime router first, so /containers/runtime/start isn't read as a container ref.
    app.include_router(containers.runtime_router, prefix="/api", dependencies=[require_user])
    app.include_router(containers.router, prefix="/api", dependencies=[require_user])
    app.include_router(apps.router, prefix="/api", dependencies=[require_user])
    app.include_router(store_api.router, prefix="/api", dependencies=[require_user])
    app.include_router(settings_api.router, prefix="/api", dependencies=[require_user])

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
