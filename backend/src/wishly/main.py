"""Application entrypoint.

Run locally with:  uv run uvicorn wishly.main:app --reload
"""

from fastapi import FastAPI

from wishly import health
from wishly.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build a configured app. Tests call this with their own Settings."""
    settings = settings or Settings()

    app = FastAPI(
        title="Wishly API",
        version=settings.version,
        # Interactive docs are handy locally but are free reconnaissance in prod.
        docs_url=None if settings.env == "prod" else "/docs",
        redoc_url=None,
        openapi_url=None if settings.env == "prod" else "/openapi.json",
    )
    # Anything that needs config reads it from here: request.app.state.settings
    app.state.settings = settings

    app.include_router(health.router)
    return app


app = create_app()
