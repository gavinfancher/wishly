"""Reminder lead-times sub-resource (PLAN T3.3).

``PUT /events/{id}/reminders`` replaces the *entire* set of ``event_reminders``
for an event with the supplied ``days_before`` list. Uniqueness of
``days_before`` per event is enforced both in the schema and by the DB unique
constraint ``(event_id, days_before)``.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from wishly.api.deps import CurrentUser, DBSession
from wishly.api.errors import not_found
from wishly.api.schemas import RemindersOut, RemindersReplace
from wishly.core.logging import get_logger
from wishly.db.models import Event, EventReminder

logger = get_logger("wishly.api.reminders")

router = APIRouter(prefix="/events", tags=["reminders"])


async def _assert_owned_event(session: AsyncSession, event_id: uuid.UUID, user_id: str) -> None:
    """Raise 404 unless ``event_id`` exists and belongs to ``user_id``."""
    stmt = select(Event.id).where(Event.id == event_id, Event.user_id == user_id)
    if (await session.execute(stmt)).scalar_one_or_none() is None:
        raise not_found("Event not found.")


async def _current_days(session: AsyncSession, event_id: uuid.UUID) -> list[int]:
    """The event's reminder lead times, sorted ascending."""
    stmt = (
        select(EventReminder.days_before)
        .where(EventReminder.event_id == event_id)
        .order_by(EventReminder.days_before)
    )
    return list((await session.execute(stmt)).scalars().all())


@router.get("/{event_id}/reminders", response_model=RemindersOut)
async def get_reminders(
    event_id: uuid.UUID, principal: CurrentUser, session: DBSession
) -> RemindersOut:
    """Return the reminder lead times for an owned event."""
    await _assert_owned_event(session, event_id, principal.sub)
    return RemindersOut(event_id=event_id, days_before=await _current_days(session, event_id))


@router.put("/{event_id}/reminders", response_model=RemindersOut)
async def replace_reminders(
    event_id: uuid.UUID,
    body: RemindersReplace,
    principal: CurrentUser,
    session: DBSession,
) -> RemindersOut:
    """Replace the full set of reminder lead times for an owned event.

    The request is idempotent: the existing reminders are deleted and the new
    set inserted within the request transaction. Duplicate ``days_before`` are
    rejected by the schema before we reach the database.
    """
    await _assert_owned_event(session, event_id, principal.sub)

    # Replace-set semantics: clear then insert. ``selectinload`` keeps the ORM
    # relationship consistent if it was already loaded elsewhere in the request.
    await session.execute(delete(EventReminder).where(EventReminder.event_id == event_id))
    for day in body.days_before:
        session.add(EventReminder(event_id=event_id, days_before=day))
    await session.flush()

    logger.info(
        "reminders replaced",
        extra={
            "user_id": principal.sub,
            "event_id": str(event_id),
            "days_before": sorted(body.days_before),
            "count": len(body.days_before),
        },
    )

    # Re-read through the relationship to keep any cached Event object fresh.
    event = (
        await session.execute(
            select(Event).where(Event.id == event_id).options(selectinload(Event.reminders))
        )
    ).scalar_one_or_none()
    days = sorted(r.days_before for r in event.reminders) if event is not None else []
    return RemindersOut(event_id=event_id, days_before=days)
