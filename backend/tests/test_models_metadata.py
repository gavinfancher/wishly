"""Smoke tests for the ORM model metadata.

These tests do not need a live database: they assert that the models import,
that every table from ``docs/PLAN.md`` §6 is registered on the shared metadata
with its key constraints/indexes, and that the metadata can be materialised
against a throwaway SQLite engine.
"""

from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "postgresql://wishly:wishly@localhost:5432/wishly")

from sqlalchemy import create_engine, inspect  # noqa: E402

from wishly.db import models  # noqa: E402
from wishly.db.base import Base  # noqa: E402

EXPECTED_TABLES = {
    "users",
    "events",
    "event_reminders",
    "templates",
    "notification_log",
    "suppressions",
}


def test_all_tables_registered() -> None:
    assert set(Base.metadata.tables) >= EXPECTED_TABLES


def test_models_exported() -> None:
    for name in ("User", "Event", "EventReminder", "Template", "NotificationLog", "Suppression"):
        assert hasattr(models, name)


def test_event_indexes_present() -> None:
    events = Base.metadata.tables["events"]
    index_names = {ix.name for ix in events.indexes}
    assert {"events_user_id_idx", "events_month_day_idx"} <= index_names


def test_notification_log_dedupe_unique() -> None:
    nl = Base.metadata.tables["notification_log"]
    unique_cols = [
        tuple(c.name for c in con.columns)
        for con in nl.constraints
        if con.__class__.__name__ == "UniqueConstraint"
    ]
    assert ("event_id", "days_before", "occurrence_date") in unique_cols


def test_metadata_create_all_sqlite() -> None:
    """The full schema materialises against a throwaway SQLite engine.

    Postgres-only artefacts (``gen_random_uuid()`` defaults, the partial index'
    ``WHERE`` clause) are tolerated by SQLite at CREATE time; this just proves the
    metadata is internally consistent and emittable.
    """
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    created = set(inspect(engine).get_table_names())
    assert created >= EXPECTED_TABLES
    Base.metadata.drop_all(engine)
    engine.dispose()
