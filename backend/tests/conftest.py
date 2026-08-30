"""Shared test fixtures for non-API tests."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

os.environ.setdefault("DATABASE_URL", "postgresql://wishly:wishly@localhost:5432/wishly_test")

# Tests must never inherit the developer's backend/.env: it commonly carries
# AUTH_DEV_BYPASS=true, which would authenticate every request as the fixed dev
# user and quietly turn the 401 tests green for the wrong reason. Real env vars
# win over the .env file, so setting it here neutralises the file.
os.environ["AUTH_DEV_BYPASS"] = "false"
os.environ.setdefault("ENVIRONMENT", "dev")


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

# The production schema. Tests build their database from the very same file that
# provisions RDS, so a model that has drifted from it fails here rather than in
# production. There are no migrations to run first.
SCHEMA_SQL = Path(__file__).resolve().parents[2] / "infra" / "sql" / "schema.sql"


@pytest.fixture(scope="session", autouse=True)
def _create_schema() -> None:
    """Apply infra/sql/schema.sql to the test database (idempotent)."""
    engine = get_sync_engine()
    with engine.begin() as conn:
        conn.exec_driver_sql(SCHEMA_SQL.read_text())


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
