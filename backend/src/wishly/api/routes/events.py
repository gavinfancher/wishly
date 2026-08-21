"""Events CRUD, scoped to the authenticated user (PLAN T3.2).

Every query is filtered by ``user_id == principal.sub`` so a user can only ever
see or mutate their own events. A request for an event owned by someone else is
indistinguishable from one that does not exist: both return **404**.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from wishly.api import crud
from wishly.api.deps import CurrentUser, DBSession
from wishly.api.errors import not_found, unprocessable
from wishly.api.schemas import EventCreate, EventOut, EventUpdate, check_month_day
from wishly.db.models import Event

router = APIRouter(prefix="/events", tags=["events"])


async def _get_owned_event(session: AsyncSession, event_id: uuid.UUID, user_id: str) -> Event:
    """Load an event by id **scoped to its owner**, or raise 404.

    Reminders are eagerly loaded so the response can include their lead times.
    """
    stmt = (
        select(Event)
        .where(Event.id == event_id, Event.user_id == user_id)
        .options(selectinload(Event.reminders))
    )
    event = (await session.execute(stmt)).scalar_one_or_none()
    if event is None:
        raise not_found("Event not found.")
    return event


def _to_out(event: Event) -> EventOut:
    """Serialise an event (with its reminder lead times) to the response model."""
    # EventOut coerces the ORM ``reminders`` relationship to its days_before
    # values (see schemas.EventOut._reminder_days), so no post-fixup is needed.
    return EventOut.model_validate(event)


@router.get("", response_model=list[EventOut])
async def list_events(principal: CurrentUser, session: DBSession) -> list[EventOut]:
    """List the current user's events, newest first."""
    stmt = (
        select(Event)
        .where(Event.user_id == principal.sub)
        .options(selectinload(Event.reminders))
        .order_by(Event.created_at.desc())
    )
    events = (await session.execute(stmt)).scalars().all()
    return [_to_out(e) for e in events]


@router.post("", response_model=EventOut, status_code=status.HTTP_201_CREATED)
async def create_event(body: EventCreate, principal: CurrentUser, session: DBSession) -> EventOut:
    """Create an event owned by the current user."""
    # Provision the owner row so the FK holds even before the first ``GET /me``.
    await crud.provision_user(session, principal)

    event = Event(
        user_id=principal.sub,
        title=body.title,
        event_type=body.event_type.value,
        event_month=body.event_month,
        event_day=body.event_day,
        event_year=body.event_year,
        message=body.message,
        recipient_email=body.recipient_email,
        recipient_name=body.recipient_name,
        template_id=body.template_id,
        is_active=body.is_active,
    )
    session.add(event)
    await session.flush()
    await session.refresh(event, attribute_names=["reminders"])
    return _to_out(event)


@router.get("/{event_id}", response_model=EventOut)
async def get_event(event_id: uuid.UUID, principal: CurrentUser, session: DBSession) -> EventOut:
    """Fetch a single owned event (404 if missing or owned by another user)."""
    event = await _get_owned_event(session, event_id, principal.sub)
    return _to_out(event)


@router.patch("/{event_id}", response_model=EventOut)
async def update_event(
    event_id: uuid.UUID,
    body: EventUpdate,
    principal: CurrentUser,
    session: DBSession,
) -> EventOut:
    """Partially update an owned event."""
    event = await _get_owned_event(session, event_id, principal.sub)

    updates = body.updated_fields()
    if "event_type" in updates and updates["event_type"] is not None:
        # Pydantic gives us the enum; persist its string value.
        updates["event_type"] = body.event_type.value if body.event_type else None

    # Validate the *resulting* calendar day: a partial update that changes only
    # the month or only the day must still land on a real date (Feb 29 allowed).
    new_month = body.event_month if body.event_month is not None else event.event_month
    new_day = body.event_day if body.event_day is not None else event.event_day
    try:
        check_month_day(new_month, new_day)
    except ValueError as exc:
        raise unprocessable(str(exc)) from exc

    for field, value in updates.items():
        setattr(event, field, value)

    await session.flush()
    await session.refresh(event, attribute_names=["reminders"])
    return _to_out(event)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(event_id: uuid.UUID, principal: CurrentUser, session: DBSession) -> None:
    """Delete an owned event (cascades to its reminders and notification log)."""
    event = await _get_owned_event(session, event_id, principal.sub)
    await session.delete(event)
    await session.flush()
