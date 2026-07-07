"""Seed system email templates into Postgres (PLAN T1.4).

Inserts the three built-in templates (birthday, anniversary, custom) with
``user_id = null``. HTML is read from :mod:`wishly.email.templates`; subjects
match :mod:`wishly.email.render`.

Run idempotently::

    uv run python -m wishly.db.seed
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from sqlalchemy import CursorResult, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from wishly.db.models import Template
from wishly.db.session import get_sync_sessionmaker
from wishly.email.render import _SUBJECT_BY_EVENT_TYPE

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "email" / "templates"

# Stable system template names — used for idempotent upsert.
_SYSTEM = (
    ("birthday", "birthday.html.j2"),
    ("anniversary", "anniversary.html.j2"),
    ("custom", "custom.html.j2"),
)


def _load_html(filename: str) -> str:
    path = _TEMPLATES_DIR / filename
    return path.read_text(encoding="utf-8")


def seed_system_templates(session: Session) -> int:
    """Insert any missing system templates. Returns the number of rows inserted."""
    inserted = 0
    for name, filename in _SYSTEM:
        existing = session.execute(
            select(Template.id).where(Template.user_id.is_(None), Template.name == name)
        ).scalar_one_or_none()
        if existing is not None:
            continue

        subject = _SUBJECT_BY_EVENT_TYPE.get(name, "Reminder: {{ title }} is {{ days_phrase }}")
        html = _load_html(filename)
        stmt = (
            pg_insert(Template)
            .values(user_id=None, name=name, subject=subject, html=html)
            .on_conflict_do_nothing()
        )
        result = cast("CursorResult[Any]", session.execute(stmt))
        if result.rowcount:
            inserted += 1
    return inserted


def main() -> None:
    """CLI entry: seed templates and commit."""
    factory = get_sync_sessionmaker()
    with factory() as session:
        count = seed_system_templates(session)
        session.commit()
    print(f"seed complete ({count} template(s) inserted)")


if __name__ == "__main__":
    main()
