"""Application entrypoint.

Run locally with:  uv run uvicorn wishly.main:create_app --factory --reload

--factory makes uvicorn call create_app() itself, so importing this module
(as the tests do) never builds an app or needs a database URL.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from wishly import api, auth, email, health, ping
from wishly.db import create_pool
from wishly.ratelimit import RateLimiter
from wishly.scheduler import Scheduler
from wishly.settings import Settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Runs once at startup (before the yield) and once at shutdown (after)."""
    # wait=False: connect in the background. If the database is down, the app
    # still starts — /healthz answers, /readyz reports the problem — instead of
    # crash-looping.
    app.state.pool.open(wait=False)
    if app.state.settings.scheduler_enabled:
        # Looks send_email up on each call, so a replacement (tests) takes effect.
        app.state.scheduler = Scheduler(
            app.state.pool, send_email=lambda **e: app.state.send_email(**e)
        )
        app.state.scheduler.start()
    yield
    if app.state.scheduler is not None:
        app.state.scheduler.stop()
    app.state.pool.close()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build a configured app. Tests call this with their own Settings."""
    settings = settings or Settings()
    # Our own loggers (e.g. the scheduler's "scheduled send" line) go to stderr
    # alongside uvicorn's, where `kubectl logs` picks them up. No-op if logging
    # is already configured.
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s: %(message)s")

    app = FastAPI(
        title="Wishly API",
        version=settings.version,
        lifespan=lifespan,
        # Interactive docs are handy locally but are free reconnaissance in prod.
        docs_url=None if settings.env == "prod" else "/docs",
        redoc_url=None,
        openapi_url=None if settings.env == "prod" else "/openapi.json",
    )
    # Anything that needs config, the database, or email reads it from app.state.
    app.state.settings = settings
    app.state.pool = create_pool(settings)
    app.state.send_email = (
        partial(email.send_via_resend, settings) if settings.resend_api_key else email.print_email
    )
    app.state.scheduler = None  # started by lifespan, if enabled
    app.state.ping_limiter = RateLimiter(limit=ping.PINGS_PER_MINUTE, window_seconds=60)

    # The frontend lives on a different origin, so browsers need CORS headers
    # before they'll let it read our responses.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type"],
    )

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(api.router)
    app.include_router(ping.router)
    return app
