"""Shared test fixtures for non-API tests."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

os.environ.setdefault("DATABASE_URL", "postgresql://wishly:wishly@localhost:5432/wishly_test")

# SAFETY INTERLOCK. These fixtures TRUNCATE every table, so they must never point
# at a real database. A previous configuration defaulted to the development
# database and silently wiped live data on every test run; refusing to start is
# the only reliable prevention, because the damage is invisible until someone
# notices their rows are gone.
_dsn = os.environ["DATABASE_URL"]
if not _dsn.rsplit("/", 1)[-1].split("?")[0].endswith("_test"):
    raise RuntimeError(
        f"Refusing to run: DATABASE_URL must name a database ending in '_test', got {_dsn!r}. "
        "These tests truncate every table."
    )


from wishly.db.session import get_sync_engine  # noqa: E402

_TABLES = (
    "notification_log",
    "event_reminders",
    "events",
    "templates",
    "suppressions",
    "users",
)


@pytest.fixture
def sync_session() -> Iterator[Session]:
    """A sync session against local Postgres with clean tables."""
    engine = get_sync_engine()
    with engine.begin() as conn:
        conn.execute(text(f"truncate {', '.join(_TABLES)} restart identity cascade"))

    factory = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        with engine.begin() as conn:
            conn.execute(text(f"truncate {', '.join(_TABLES)} restart identity cascade"))
        engine.dispose()
