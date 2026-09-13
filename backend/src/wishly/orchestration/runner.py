"""The hourly send: one function, and a ``__main__`` for running it by hand.

:func:`send_reminders` chains the two steps in :mod:`wishly.orchestration.tasks`
— find what is due, then claim/send/record it. The send carries its own retry
policy for transient Resend errors (see ``_send_with_retry`` there).

The tick is a plain hourly one: per-user ``send_hour`` gating happens inside
:func:`~wishly.orchestration.tasks.compute_due_notifications`, so nothing here
needs to know about timezones.

**What runs it.** An EventBridge scheduled rule POSTs to
``/internal/runs/send-reminders`` every hour through the Cloudflare Tunnel; the
route hands this function to a background task and returns 202 immediately (an
EventBridge API destination times out after 5 seconds, and one Resend call is
allowed 30). See ``infra/terraform/schedule.tf``.

**Where the schedule lives.** Only in terraform. This module used to carry an
``HOURLY_CRON`` constant *and* register it with Prefect Cloud on startup, which
meant the answer to "when does this run" depended on which process last called
``serve()``. Now there is one answer, in one file, under version control.

To run the send once without a scheduler — a shell, a test, a missed hour —
call :func:`send_reminders` directly or run ``python -m
wishly.orchestration.runner``.
"""

from __future__ import annotations

from wishly.core.logging import get_logger
from wishly.orchestration.tasks import find_due_notifications, send_due_notifications

logger = get_logger("wishly.orchestration")


def send_reminders() -> dict[str, int]:
    """Find every reminder due this hour and send it exactly once.

    Returns the tally by outcome (``sent`` / ``skipped`` / ``duplicate`` /
    ``failed``). Never raises for a send failure: those are recorded against
    their ``notification_log`` row and counted, because the caller is a
    background task whose exception nobody would see.
    """
    due = find_due_notifications()
    tally = send_due_notifications(due)
    logger.info("send_reminders complete: %s", tally)
    return tally


if __name__ == "__main__":  # pragma: no cover - manual entrypoint
    from wishly.core.logging import configure_logging

    configure_logging()
    print(send_reminders())


__all__ = ["send_reminders"]
