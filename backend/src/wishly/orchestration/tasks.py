"""The hourly send pipeline (T5.2 + T5.3).

Two steps, wired together in :mod:`wishly.orchestration.runner`:

#. :func:`find_due_notifications` — implements PLAN §7 steps 1-3: select the
   users in their send window (local hour == ``send_hour``), then, for each
   active event and each configured lead time, decide whether a reminder is due
   this run. Emits a list of :class:`DueNotification` (plain, serializable data
   — never detached ORM objects).
#. :func:`send_due_notifications` — implements PLAN §7 steps 4-6 for each due
   item: **claim** a row in ``notification_log`` via
   ``insert ... on conflict do nothing returning id`` (winning the insert grants
   the right to send), skip if already claimed or the recipient is suppressed,
   then render + send and record ``sent``/``failed`` on the same claimed row.

The claim-before-send protocol is what makes double-sends structurally
impossible, so retries (T5.4) update the existing row instead of duplicating.
It is also what makes the HTTP trigger safe: EventBridge delivering the same
tick twice, or the VM and the ECS standby both answering, costs a wasted query
and nothing else.

**No Prefect.** This used to be two ``@task``-decorated functions whose retries
came from the flow runner. The retry now lives in :func:`_send_with_retry`,
which is a straight improvement: it retries the one send that failed instead of
re-walking the whole batch, and it consults ``EmailSendError.transient`` so a
hard validation error fails immediately rather than three times.
"""

import datetime
import random
import time
from dataclasses import dataclass

import pendulum
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from wishly.core.logging import get_logger
from wishly.db.models import Event, NotificationLog, Suppression, User
from wishly.db.session import session_scope
from wishly.email.render import build_manage_url, render_email
from wishly.email.resend_client import EmailSendError, ResendClient
from wishly.orchestration.due import is_in_send_window, local_today, occurrence_on

logger = get_logger("wishly.orchestration")

# Transient Resend failures (rate limits, upstream 5xx, network) are worth a few
# quick retries; the claim row already exists, so a retry updates it in place.
# Exponential backoff, jittered so concurrent retries do not align.
#
# The whole budget is bounded at 2 + 4 + 8 = 14s plus jitter, per notification.
# That matters now that the send runs in the API process rather than a Prefect
# subprocess: it is a threadpool worker being held, so it must end on its own.
SEND_RETRIES = 3
SEND_RETRY_DELAYS = [2.0, 4.0, 8.0]
SEND_RETRY_JITTER = 0.5


@dataclass(frozen=True)
class DueNotification:
    """A single reminder that is due to be sent on this run.

    Carries only scalar fields (safe to pass between tasks / serialize); the
    recipient is *not* yet resolved here so suppression + resolution happen
    together at send time against fresh DB state.
    """

    event_id: str  # str form of the event UUID (serializable across op boundaries)
    days_before: int
    occurrence_date: datetime.date
    event_type: str
    title: str
    message: str | None
    # Owner identity + per-event overrides; resolved to a concrete recipient at
    # send time (recipient_email or user.email; recipient_name or first_name).
    user_id: str
    owner_email: str
    owner_first_name: str | None
    recipient_email: str | None
    recipient_name: str | None

    def resolved_email(self) -> str:
        """The address to send to: the event override, else the account owner."""
        return self.recipient_email or self.owner_email

    def resolved_name(self) -> str:
        """The greeting name: the event override, else the owner's first name."""
        return self.recipient_name or self.owner_first_name or "there"


def compute_due_notifications(
    session: Session, now_utc: datetime.datetime
) -> list[DueNotification]:
    """Pure-ish core of :func:`find_due_notifications` (no Prefect context).

    Queries non-deleted users whose local hour matches ``send_hour``, then walks
    their active events and reminders applying :func:`occurrence_on`. Split out
    from the op so it is directly unit-testable against a real session.
    """
    # Step 1: users in their send window this run. Cheap to evaluate the window
    # in Python so DST/zone math stays in pendulum rather than SQL.
    users = session.execute(select(User).where(User.deleted_at.is_(None))).scalars().all()
    windowed = [u for u in users if is_in_send_window(now_utc, u.timezone, u.send_hour)]
    if not windowed:
        return []

    due: list[DueNotification] = []
    for user in windowed:
        today = local_today(now_utc, user.timezone)  # Step 2: local date.
        events = (
            session.execute(
                select(Event)
                .where(Event.user_id == user.id, Event.is_active.is_(True))
                .order_by(Event.id)
            )
            .scalars()
            .all()
        )
        for event in events:
            for reminder in event.reminders:
                # Step 3: is this lead time due today? (Feb 29 -> Feb 28 inside.)
                occurrence = occurrence_on(
                    today,
                    reminder.days_before,
                    event.event_month,
                    event.event_day,
                )
                if occurrence is None:
                    continue
                due.append(
                    DueNotification(
                        event_id=str(event.id),
                        days_before=reminder.days_before,
                        occurrence_date=occurrence,
                        event_type=event.event_type,
                        title=event.title,
                        message=event.message,
                        user_id=user.id,
                        owner_email=user.email,
                        owner_first_name=user.first_name,
                        recipient_email=event.recipient_email,
                        recipient_name=event.recipient_name,
                    )
                )
    return due


def find_due_notifications() -> list[DueNotification]:
    """Return the reminders due as of ``now`` (PLAN §7 steps 1-3)."""
    now_utc = pendulum.now("UTC")
    with session_scope() as session:
        due = compute_due_notifications(session, now_utc)
    logger.info("found %d due notification(s)", len(due))
    return due


def _claim(session: Session, item: DueNotification) -> str | None:
    """Attempt to claim the send by winning the idempotency insert.

    ``insert ... on conflict (event_id, days_before, occurrence_date) do nothing
    returning id``. Returns the new row id on a win, or ``None`` if the row
    already existed (already handled this occurrence) — the dedupe guarantee.
    """
    stmt = (
        pg_insert(NotificationLog)
        .values(
            event_id=item.event_id,
            days_before=item.days_before,
            occurrence_date=item.occurrence_date,
            status="pending",
        )
        .on_conflict_do_nothing(
            index_elements=["event_id", "days_before", "occurrence_date"],
        )
        .returning(NotificationLog.id)
    )
    claimed_id = session.execute(stmt).scalar_one_or_none()
    return str(claimed_id) if claimed_id is not None else None


def _is_suppressed(session: Session, email: str) -> bool:
    """Whether ``email`` is on the suppression list (bounce/complaint/manual)."""
    return (
        session.execute(select(Suppression.email).where(Suppression.email == email)).first()
        is not None
    )


def _mark(
    session: Session,
    claim_id: str,
    *,
    status: str,
    resend_id: str | None = None,
    error: str | None = None,
) -> None:
    """Update the claimed ``notification_log`` row to its terminal status."""
    row = session.get(NotificationLog, claim_id)
    if row is None:  # pragma: no cover - claim id always exists in normal flow
        return
    row.status = status
    row.resend_id = resend_id
    row.error = error
    if status == "sent":
        row.sent_at = pendulum.now("UTC")


def _send_with_retry(
    resend_client: ResendClient,
    *,
    to: str,
    subject: str,
    html: str,
    text: str,
) -> str:
    """Send one email, retrying only errors that might succeed next time.

    Replaces Prefect's task-level retry policy. Two differences, both deliberate:

    * The unit of retry is **one email**, not the whole batch. A rate limit on
      the third of five reminders no longer re-walks the first two.
    * ``EmailSendError.transient`` decides. A 422 for a malformed address is not
      going to become valid in four seconds, so it fails on the first attempt
      instead of burning the full backoff.

    Raises the last error once the budget is exhausted; the caller records it.
    """
    attempts = SEND_RETRIES + 1
    for attempt in range(attempts):
        try:
            return resend_client.send_email(to=to, subject=subject, html=html, text=text)
        except EmailSendError as exc:
            last = attempt == attempts - 1
            if last or not exc.transient:
                raise
            # Jitter so several reminders failing on the same rate limit do not
            # come back in lockstep and trip it again.
            delay = SEND_RETRY_DELAYS[attempt]
            delay += random.uniform(0, delay * SEND_RETRY_JITTER)  # noqa: S311 — not crypto
            logger.warning(
                "resend attempt %d/%d failed (%s); retrying in %.1fs",
                attempt + 1,
                attempts,
                exc,
                delay,
            )
            time.sleep(delay)
    raise AssertionError("unreachable")  # pragma: no cover — loop always returns or raises


def process_one(
    session: Session,
    resend_client: ResendClient,
    item: DueNotification,
) -> str:
    """Claim, (maybe) send, and record a single due notification.

    Returns a short status string (``sent`` | ``failed`` | ``skipped`` |
    ``duplicate``) for logging/metrics. Each call commits its own row so that
    one failure cannot roll back already-sent siblings, and a retry resumes
    cleanly.

    A send that fails every attempt is recorded as ``failed`` and **returned**,
    not raised. Under Prefect the raise was the retry signal; now that the batch
    is a plain loop, raising would abandon everyone queued behind a single bad
    recipient. The failure is durable in ``notification_log`` either way, which
    is where ``GET /notifications`` reads it from.
    """
    claim_id = _claim(session, item)
    if claim_id is None:
        # Lost the race / already handled this occurrence — never send twice.
        session.commit()
        return "duplicate"

    recipient = item.resolved_email()
    if _is_suppressed(session, recipient):
        _mark(session, claim_id, status="skipped", error="recipient suppressed")
        session.commit()
        return "skipped"

    rendered = render_email(
        event_type=item.event_type,
        recipient_name=item.resolved_name(),
        title=item.title,
        days_before=item.days_before,
        occurrence_date=item.occurrence_date,
        manage_url=build_manage_url(item.user_id),
        message=item.message,
    )

    try:
        resend_id = _send_with_retry(
            resend_client,
            to=recipient,
            subject=rendered.subject,
            html=rendered.html,
            text=rendered.text,
        )
    except Exception as exc:  # noqa: BLE001 — one bad send must not stop the batch
        # Record the failure on the claimed row. The claim persists, so the next
        # hour's tick sees this occurrence as already handled and will not send
        # a duplicate — a failed reminder stays failed until someone looks.
        _mark(session, claim_id, status="failed", error=str(exc))
        session.commit()
        logger.error(
            "send failed for %s/%s/%s: %s",
            item.event_id,
            item.days_before,
            item.occurrence_date.isoformat(),
            exc,
        )
        return "failed"

    _mark(session, claim_id, status="sent", resend_id=resend_id)
    session.commit()
    return "sent"


def send_due_notifications(due: list[DueNotification]) -> dict[str, int]:
    """Claim + send + record every due notification (PLAN §7 steps 4-6).

    Returns a tally of outcomes by status. Every item is attempted: a failure is
    recorded against its claimed row and counted, and the loop continues. The
    per-send retry lives in :func:`_send_with_retry`.
    """
    client = ResendClient()
    tally: dict[str, int] = {"sent": 0, "skipped": 0, "duplicate": 0, "failed": 0}

    # One session for the op; ``process_one`` commits each item independently so
    # a later failure cannot roll back an already-sent sibling.
    with session_scope() as session:
        for item in due:
            outcome = process_one(session, client, item)
            tally[outcome] = tally.get(outcome, 0) + 1
            logger.info(
                "notification %s/%s/%s -> %s",
                item.event_id,
                item.days_before,
                item.occurrence_date.isoformat(),
                outcome,
            )

    logger.info("send tally: %s", tally)
    return tally


__all__ = [
    "SEND_RETRIES",
    "SEND_RETRY_DELAYS",
    "SEND_RETRY_JITTER",
    "DueNotification",
    "compute_due_notifications",
    "find_due_notifications",
    "process_one",
    "send_due_notifications",
]
