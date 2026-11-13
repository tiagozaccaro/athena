"""FastAPI application: the API under /api, and the exported web UI at /."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from athena import __version__
from athena.api import system
from athena.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(
        title="Athena",
        version=__version__,
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url=None,
    )
    app.state.settings = settings
    app.include_router(system.router, prefix="/api")

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
