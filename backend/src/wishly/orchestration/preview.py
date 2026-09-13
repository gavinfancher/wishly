"""Manually-triggered preview of the reminder pipeline.

The hourly send (:mod:`wishly.orchestration.runner`) only sends when a reminder
is genuinely due, which makes it useless for checking your work: the next real
send may be months away. This exercises the same path on demand — load a user
and event from Postgres, render the real template, and optionally hand it to
Resend — so you can see exactly what lands in the inbox.

Reached over HTTP at ``POST /internal/runs/preview``, which is what replaced the
"run deployment with parameters" button in the Prefect UI. It runs inline rather
than in the background: a human is waiting for the rendered subject line, and no
5-second API-destination timeout applies to a curl.

**It never writes to ``notification_log``.** That table is the idempotency
ledger: the sender only sends after winning
``insert ... on conflict (event_id, days_before, occurrence_date) do nothing``,
so a synthetic row there would make a *real* reminder for the same occurrence
look already-sent and silently suppress it. Sends are recorded in
``test_email_log`` instead, exactly as the ``/me/test-email`` endpoint does.

``send`` defaults to **False** so calling this with stock parameters renders and
returns the email without touching Resend. Pass ``send=true`` when you actually
want the message delivered.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

import pendulum
from sqlalchemy import select
from sqlalchemy.orm import Session

from wishly.core.logging import get_logger
from wishly.db.models import Event, TestEmailLog, User
from wishly.db.session import session_scope
from wishly.email.render import build_manage_url, render_email
from wishly.email.resend_client import EmailSendError, ResendClient
from wishly.orchestration.due import local_today

# Matches the default lead time the /me/test-email endpoint previews with.
DEFAULT_DAYS_BEFORE = 7

logger = get_logger("wishly.orchestration.preview")


class PreviewError(RuntimeError):
    """Raised when the requested user/event cannot be resolved.

    Carries an operator-facing message: this is triggered by a human with curl,
    so the failure text is the whole diagnostic and the route returns it verbatim.
    """


def next_occurrence(today: datetime.date, event_month: int, event_day: int) -> pendulum.Date:
    """The next date on/after ``today`` that the event falls on.

    Mirrors the Feb 29 rule in :func:`wishly.orchestration.due.occurrence_on`: in
    a non-leap year a Feb 29 event is observed on Feb 28. Unlike ``occurrence_on``
    this never returns ``None`` — a preview must always have something to render,
    even for an event 200 days out.
    """

    def _on(year: int) -> pendulum.Date:
        if (event_month, event_day) == (2, 29) and not pendulum.date(year, 1, 1).is_leap_year():
            return pendulum.date(year, 2, 28)
        return pendulum.date(year, event_month, event_day)

    candidate = _on(today.year)
    return candidate if candidate >= today else _on(today.year + 1)


@dataclass(frozen=True)
class PreviewTarget:
    """The resolved user + event a preview will be rendered for."""

    user_id: str
    user_email: str
    user_first_name: str | None
    timezone: str
    event_id: str
    event_type: str
    title: str
    message: str | None
    event_month: int
    event_day: int
    recipient_email: str | None
    recipient_name: str | None


def resolve_target(
    session: Session, *, user_email: str | None, event_id: str | None
) -> PreviewTarget:
    """Pick the user and event to preview, or explain why it is ambiguous.

    Both arguments are optional so the deployment can be triggered with no
    parameters at all on a single-user development database. Split out from the
    route so the resolution rules are unit-testable without an HTTP client.
    """
    user_stmt = select(User).where(User.deleted_at.is_(None))
    if user_email is not None:
        user_stmt = user_stmt.where(User.email == user_email)
    users = session.execute(user_stmt.order_by(User.created_at)).scalars().all()

    if not users:
        raise PreviewError(
            f"no active user matches {user_email!r}"
            if user_email
            else "no active users in this database"
        )
    if user_email is None and len(users) > 1:
        # Guessing here would email a real person who did not ask for it.
        raise PreviewError(
            "several users exist; pass user_email explicitly. Candidates: "
            + ", ".join(u.email for u in users[:10])
        )
    user = users[0]

    event_stmt = select(Event).where(Event.user_id == user.id, Event.is_active.is_(True))
    if event_id is not None:
        event_stmt = event_stmt.where(Event.id == event_id)
    events = session.execute(event_stmt.order_by(Event.created_at)).scalars().all()

    if not events:
        raise PreviewError(
            f"user {user.email} has no active event with id {event_id!r}"
            if event_id
            else f"user {user.email} has no active events to preview"
        )
    event = events[0]

    return PreviewTarget(
        user_id=user.id,
        user_email=user.email,
        user_first_name=user.first_name,
        timezone=user.timezone,
        event_id=str(event.id),
        event_type=event.event_type,
        title=event.title,
        message=event.message,
        event_month=event.event_month,
        event_day=event.event_day,
        recipient_email=event.recipient_email,
        recipient_name=event.recipient_name,
    )


def preview_reminder(
    user_email: str | None = None,
    event_id: str | None = None,
    days_before: int = DEFAULT_DAYS_BEFORE,
    to: str | None = None,
    send: bool = False,
) -> dict[str, object]:
    """Render (and optionally send) one reminder on demand.

    Args:
        user_email: Which user to preview as. Optional only when the database
            holds exactly one active user.
        event_id: Which event to render. Defaults to the user's oldest active event.
        days_before: Lead time to render — changes the countdown wording.
        to: Override the recipient. Defaults to the same address the real
            pipeline would use (event override, else the account owner).
        send: When False (default) render only; when True actually call Resend
            and record the result in ``test_email_log``.

    Returns:
        A summary dict: resolved recipient, subject, occurrence date, and outcome.
    """
    with session_scope() as session:
        target = resolve_target(session, user_email=user_email, event_id=event_id)

        today = local_today(pendulum.now("UTC"), target.timezone)
        occurrence = next_occurrence(today, target.event_month, target.event_day)
        recipient = to or target.recipient_email or target.user_email
        greeting = target.recipient_name or target.user_first_name or "there"

        rendered = render_email(
            event_type=target.event_type,
            recipient_name=greeting,
            title=target.title,
            days_before=days_before,
            occurrence_date=occurrence,
            manage_url=build_manage_url(target.user_id),
            message=target.message,
        )

        logger.info(
            "previewing %r for %s (occurrence %s, %d days before)",
            target.title,
            recipient,
            occurrence.isoformat(),
            days_before,
        )

        # Prefect published the plaintext body as a run artifact so you could
        # read it without opening an inbox. The route returns it in the response
        # instead, which is the same thing one indirection shorter.
        summary: dict[str, object] = {
            "text": rendered.text,
            "user_email": target.user_email,
            "event_id": target.event_id,
            "title": target.title,
            "recipient": recipient,
            "subject": rendered.subject,
            "occurrence_date": occurrence.isoformat(),
            "days_before": days_before,
            "html_bytes": len(rendered.html),
        }

        if not send:
            summary["outcome"] = "rendered"
            logger.info("send=False — not calling Resend. Set send=True to deliver.")
            return summary

        try:
            resend_id = ResendClient().send_email(
                to=recipient,
                subject=rendered.subject,
                html=rendered.html,
                text=rendered.text,
            )
        except EmailSendError as exc:
            # Record the failure: a test that never arrived is exactly what you
            # want visible afterwards.
            session.add(
                TestEmailLog(user_id=target.user_id, status="failed", error=str(exc)[:2000])
            )
            session.commit()
            logger.error("Resend rejected the preview: %s", exc)
            raise

        session.add(
            TestEmailLog(
                user_id=target.user_id,
                status="sent",
                resend_id=resend_id,
                sent_at=pendulum.now("UTC"),
            )
        )
        session.commit()

        summary["outcome"] = "sent"
        summary["resend_id"] = resend_id
        logger.info("sent to %s (resend id %s)", recipient, resend_id)
        return summary


if __name__ == "__main__":  # pragma: no cover - manual local run
    preview_reminder()


__all__ = [
    "DEFAULT_DAYS_BEFORE",
    "PreviewError",
    "PreviewTarget",
    "next_occurrence",
    "preview_reminder",
    "resolve_target",
]
