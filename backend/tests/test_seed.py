"""Tests for system template seeding (T1.4)."""

from __future__ import annotations

from sqlalchemy import select

from wishly.db.models import Template
from wishly.db.seed import seed_system_templates


def test_seed_system_templates_is_idempotent(sync_session) -> None:
    first = seed_system_templates(sync_session)
    sync_session.commit()
    assert first == 3

    second = seed_system_templates(sync_session)
    sync_session.commit()
    assert second == 0

    rows = (
        sync_session.execute(
            select(Template).where(Template.user_id.is_(None)).order_by(Template.name)
        )
        .scalars()
        .all()
    )
    assert [r.name for r in rows] == ["anniversary", "birthday", "custom"]
    assert all(r.subject and r.html for r in rows)
