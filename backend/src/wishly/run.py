"""POST /internal/run — EventBridge calls this at the top of every hour.

For each reminder that's due (see schedule.py):
  1. claim it by inserting its row into `sends`. If the row already exists,
     another run got there first, so skip it.
  2. send the email.
  3. if sending failed, delete the claim so the next run can try again.
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request
from psycopg import Connection

from wishly.auth import require_run_token
from wishly.db import get_conn
from wishly.schedule import due_occurrence

log = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_run_token)])


@router.post("/internal/run")
def run(request: Request, conn: Annotated[Connection, Depends(get_conn)]) -> dict[str, int]:
    return send_due_reminders(conn, request.app.state.send_email, now=datetime.now(UTC))


def send_due_reminders(conn: Connection, send_email: Callable, now: datetime) -> dict[str, int]:
    # Housekeeping while we're here: expired sessions can never be used again.
    conn.execute("delete from sessions where expires_at < %s", (now,))

    rows = conn.execute(
        """
        select r.id, r.title, r.month, r.day, r.days_before,
               u.email, u.timezone, u.send_hour
        from reminders r join users u on u.id = r.user_id
        where u.onboarded_at is not null
        """
    ).fetchall()

    sent = failed = 0
    for row in rows:
        for days_before in row["days_before"]:
            occurrence = due_occurrence(
                month=row["month"],
                day=row["day"],
                days_before=days_before,
                send_hour=row["send_hour"],
                tz=ZoneInfo(row["timezone"]),
                now=now,
            )
            if occurrence is None:
                continue

            key = {"id": row["id"], "days_before": days_before, "occurrence": occurrence}
            claimed = conn.execute(
                """
                insert into sends (reminder_id, days_before, occurrence_date)
                values (%(id)s, %(days_before)s, %(occurrence)s)
                on conflict do nothing
                """,
                key,
            ).rowcount
            if not claimed:
                continue

            try:
                send_email(
                    to=row["email"],
                    subject=subject_line(row["title"], days_before),
                    text=f"{row['title']} is on {occurrence:%B} {occurrence.day}.\n\n— Wishly",
                    idempotency_key=f"{row['id']}/{days_before}/{occurrence}",
                )
                sent += 1
            except Exception:
                log.exception("send failed for reminder %s", row["id"])
                conn.execute(
                    """
                    delete from sends where reminder_id = %(id)s
                    and days_before = %(days_before)s and occurrence_date = %(occurrence)s
                    """,
                    key,
                )
                failed += 1

    return {"sent": sent, "failed": failed}


def subject_line(title: str, days_before: int) -> str:
    if days_before == 0:
        return f"Today: {title}"
    if days_before == 1:
        return f"Tomorrow: {title}"
    return f"In {days_before} days: {title}"
