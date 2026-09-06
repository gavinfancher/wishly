"""FastAPI application entrypoint (PLAN T2.2 / T8.2).

Wires together CORS (from ``ALLOWED_ORIGINS``), structured logging, health
probes, and every router (``/me``, ``/events``, reminders, and the Clerk +
Resend webhooks). Run locally with::

    uv run uvicorn wishly.api.main:app --reload
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from wishly.api.middleware import RequestLoggingMiddleware
from wishly.api.routes import events as events_routes
from wishly.api.routes import me as me_routes
from wishly.api.routes import notifications as notification_routes
from wishly.api.routes import reminders as reminders_routes
from wishly.api.webhooks import clerk as clerk_webhook
from wishly.api.webhooks import resend as resend_webhook
from wishly.core.logging import configure_logging, get_logger
from wishly.core.settings import settings
from wishly.db.session import get_async_engine

logger = get_logger("wishly.api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Configure logging on startup and dispose the DB engine on shutdown."""
    configure_logging()
    logger.info(
        "api startup",
        extra={
            "environment": settings.environment,
            "allowed_origins": settings.allowed_origins,
            "clerk_frontend_api": settings.clerk_frontend_api,
        },
    )
    try:
        yield
    finally:
        # Dispose the cached async engine so connections close cleanly.
        try:
            await get_async_engine().dispose()
        except SQLAlchemyError:  # pragma: no cover — best-effort cleanup
            logger.warning("engine dispose failed", exc_info=True)


def create_app() -> FastAPI:
    """Construct and configure the FastAPI application."""
    app = FastAPI(
        title="Wishly API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(RequestLoggingMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        """Liveness probe — process is up (no dependencies checked)."""
        return {"status": "ok"}

    @app.get("/ready", tags=["health"])
    async def ready() -> dict[str, Any]:
        """Readiness probe — verifies Postgres is reachable (``select 1``)."""
        try:
            async with get_async_engine().connect() as conn:
                await conn.execute(text("select 1"))
        except SQLAlchemyError as exc:
            logger.warning("readiness check failed: db unreachable", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="database unavailable",
            ) from exc
        return {"status": "ready", "database": "ok"}

    app.include_router(me_routes.router)
    app.include_router(events_routes.router)
    app.include_router(reminders_routes.router)
    app.include_router(notification_routes.router)
    app.include_router(clerk_webhook.router)
    app.include_router(resend_webhook.router)

    return app


app = create_app()
