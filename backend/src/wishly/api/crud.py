"""Reusable persistence helpers shared by routes and webhooks.

Kept thin and side-effect-light: these issue statements against a provided
:class:`AsyncSession` but never commit — commit/rollback is owned by the
``get_session`` dependency (request scope) or the webhook handler.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from wishly.api.deps import AuthedUser
from wishly.core.logging import get_logger
from wishly.db.models import Suppression, User

logger = get_logger("wishly.api.crud")


async def get_user(session: AsyncSession, user_id: str) -> User | None:
    """Return the user row for ``user_id`` (including soft-deleted), or ``None``."""
    return await session.get(User, user_id)


async def provision_user(session: AsyncSession, principal: AuthedUser) -> User:
    """Insert-or-fetch the ``users`` row for a verified principal.

    Provision-on-first-request (PLAN §2 / T2.2): on a user's first authenticated
    call we create their row from the JWT claims. Uses an idempotent
    ``on conflict do nothing`` so a racing request (or a Clerk webhook that
    arrived first) does not error; we then read the row back.
    """
    stmt = (
        pg_insert(User)
        .values(
            id=principal.sub,
            email=principal.email,
            first_name=principal.first_name,
            last_name=principal.last_name,
        )
        .on_conflict_do_nothing(index_elements=[User.id])
        .returning(User.id)
    )
    inserted = (await session.execute(stmt)).scalar_one_or_none()
    await session.flush()
    user = await session.get(User, principal.sub)
    assert user is not None  # the insert (or a prior row) guarantees existence

    # rowcount is 1 only when the insert actually created the row. A *new* row for
    # a user who has signed in before means their previous row disappeared — which
    # also silently resets onboarded_at and cascades away their events. Logged
    # loudly because nothing in this app deletes a user, so it should never happen.
    if inserted is not None:
        logger.warning(
            "user row provisioned (new)",
            extra={"user_id": principal.sub, "created_at": str(user.created_at)},
        )
    return user


async def upsert_user_from_clerk(
    session: AsyncSession,
    *,
    user_id: str,
    email: str,
    first_name: str | None,
    last_name: str | None,
) -> None:
    """Upsert a user from a Clerk ``user.created`` / ``user.updated`` webhook.

    Updates the synced identity fields and clears any prior ``deleted_at`` (a
    re-created Clerk user reactivates the row). Onboarding-owned columns
    (``timezone``, ``send_hour``) are deliberately left untouched.
    """
    insert_stmt = pg_insert(User).values(
        id=user_id,
        email=email,
        first_name=first_name,
        last_name=last_name,
    )
    stmt = insert_stmt.on_conflict_do_update(
        index_elements=[User.id],
        set_={
            "email": insert_stmt.excluded.email,
            "first_name": insert_stmt.excluded.first_name,
            "last_name": insert_stmt.excluded.last_name,
            "deleted_at": None,
            "updated_at": dt.datetime.now(tz=dt.UTC),
        },
    )
    await session.execute(stmt)


async def soft_delete_user(session: AsyncSession, user_id: str) -> None:
    """Mark a user deleted (``user.deleted`` webhook). No-op if unknown."""
    user = await session.get(User, user_id)
    if user is not None and user.deleted_at is None:
        user.deleted_at = dt.datetime.now(tz=dt.UTC)


async def upsert_suppression(session: AsyncSession, *, email: str, reason: str) -> None:
    """Add (or refresh the reason of) a suppressed recipient address.

    Lower-cased for case-insensitive matching against recipient addresses.
    """
    normalized = email.strip().lower()
    insert_stmt = pg_insert(Suppression).values(email=normalized, reason=reason)
    stmt = insert_stmt.on_conflict_do_update(
        index_elements=[Suppression.email],
        set_={"reason": insert_stmt.excluded.reason},
    )
    await session.execute(stmt)


async def list_suppressions(session: AsyncSession) -> list[Suppression]:
    """Return all suppression rows (test/inspection helper)."""
    result = await session.execute(select(Suppression))
    return list(result.scalars().all())


def reminder_days(event: Any) -> list[int]:  # noqa: ANN401 — duck-typed ORM event
    """Sorted ``days_before`` values from an event's loaded ``reminders``."""
    return sorted(r.days_before for r in event.reminders)
