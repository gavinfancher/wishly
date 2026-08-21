"""Send-log route: ``GET /notifications``.

Reads ``notification_log`` — the same ledger the send pipeline writes to when it
claims a reminder (PLAN §7) — joined to the owning event so the UI can label each
row. Read-only: nothing here may write to that table, because it is what makes
double-sends structurally impossible.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import select

from wishly.api.deps import CurrentUser, DBSession
from wishly.api.schemas import NotificationOut
from wishly.core.logging import get_logger
from wishly.db.models import Event, NotificationLog

router = APIRouter(tags=["notifications"])
logger = get_logger("wishly.api.notifications")


@router.get("/notifications", response_model=list[NotificationOut])
async def list_notifications(
    principal: CurrentUser,
    session: DBSession,
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[NotificationOut]:
    """The current user's send log, newest first.

    Scoped by joining through ``events.user_id`` — ``notification_log`` has no
    user column of its own, so the join *is* the authorization boundary. Ordered
    by ``created_at`` rather than ``sent_at`` because a failed or still-pending
    row has no ``sent_at`` and would otherwise sort unpredictably.
    """
    stmt = (
        select(
            NotificationLog.id,
            NotificationLog.event_id,
            Event.title.label("event_title"),
            Event.event_type,
            NotificationLog.days_before,
            NotificationLog.occurrence_date,
            NotificationLog.status,
            NotificationLog.sent_at,
            NotificationLog.created_at,
        )
        .join(Event, Event.id == NotificationLog.event_id)
        .where(Event.user_id == principal.sub)
        .order_by(NotificationLog.created_at.desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).mappings().all()
    logger.info(
        "send log listed",
        extra={"user_id": principal.sub, "count": len(rows)},
    )
    return [NotificationOut.model_validate(dict(r)) for r in rows]
