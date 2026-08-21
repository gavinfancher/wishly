"""Send-log route: ``GET /notifications``.

Reads ``notification_log`` — the same ledger the send pipeline writes to when it
claims a reminder (PLAN §7) — joined to the owning event so the UI can label each
row. Read-only: nothing here may write to that table, because it is what makes
double-sends structurally impossible.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import func, literal, select

from wishly.api.deps import CurrentUser, DBSession
from wishly.api.schemas import NotificationOut
from wishly.core.logging import get_logger
from wishly.db.models import Event, NotificationLog, TestEmailLog

router = APIRouter(tags=["notifications"])
logger = get_logger("wishly.api.notifications")

#: Lead time the sample email in POST /me/test-email is rendered for.
TEST_EMAIL_DAYS_BEFORE = 7


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
    # Two sources, one chronological list. Test reminders live in their own table
    # (see TestEmailLog) so notification_log stays a pure idempotency ledger; the
    # union happens here rather than by polluting that table.
    reminders = (
        select(
            NotificationLog.id,
            NotificationLog.event_id,
            Event.title.label("event_title"),
            Event.event_type,
            NotificationLog.days_before,
            NotificationLog.occurrence_date,
            NotificationLog.status,
            literal(False).label("is_test"),
            NotificationLog.sent_at,
            NotificationLog.created_at,
        )
        .join(Event, Event.id == NotificationLog.event_id)
        .where(Event.user_id == principal.sub)
    )

    tests = select(
        TestEmailLog.id,
        literal(None).label("event_id"),
        literal("Test reminder").label("event_title"),
        literal("birthday").label("event_type"),
        literal(TEST_EMAIL_DAYS_BEFORE).label("days_before"),
        # The sample email is rendered for an occasion this many days out, so the
        # history row lines up with what actually landed in the inbox.
        (func.date(TestEmailLog.created_at) + TEST_EMAIL_DAYS_BEFORE).label("occurrence_date"),
        TestEmailLog.status,
        literal(True).label("is_test"),
        TestEmailLog.sent_at,
        TestEmailLog.created_at,
    ).where(TestEmailLog.user_id == principal.sub)

    combined = reminders.union_all(tests).subquery()
    stmt = select(combined).order_by(combined.c.created_at.desc()).limit(limit)
    rows = (await session.execute(stmt)).mappings().all()
    logger.info(
        "send log listed",
        extra={
            "user_id": principal.sub,
            "count": len(rows),
            "tests": sum(1 for r in rows if r["is_test"]),
        },
    )
    return [NotificationOut.model_validate(dict(r)) for r in rows]
