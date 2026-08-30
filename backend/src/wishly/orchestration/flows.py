"""Prefect flow for the hourly send pipeline, and the process that serves it.

:func:`send_reminders` chains the two tasks in
:mod:`wishly.orchestration.tasks`: find what is due, then claim/send/record it.
The send task carries its own retry policy for transient Resend errors.

The schedule is a plain hourly tick — per-user ``send_hour`` gating happens
inside the task, so the flow does not need to know anything about timezones.

**Running it.** ``python -m wishly.orchestration.flows`` starts a long-lived
process that registers both deployments (with their schedules) against whatever
``PREFECT_API_URL`` points at, then executes their runs in subprocesses. That is
the whole deployment story: no work pool, no separate worker, no ``prefect.yaml``.

To run the flow exactly once without registering anything — handy in a shell or a
test — call :func:`send_reminders` directly instead.
"""

from __future__ import annotations

from prefect import flow, get_run_logger, serve

from wishly.core.logging import get_logger
from wishly.orchestration.preview import DEFAULT_DAYS_BEFORE, preview_reminder
from wishly.orchestration.tasks import find_due_notifications, send_due_notifications

# Hourly tick at the top of the hour.
HOURLY_CRON = "0 * * * *"

_logger = get_logger("wishly.orchestration")


def report_failure(flow, flow_run, state) -> None:  # type: ignore[no-untyped-def]
    """Flow-level failure hook — the Prefect equivalent of a run-failure sensor.

    Fires once the send task has exhausted its retries. Logs outside the run
    context so the message still lands if the run itself is being torn down.
    """
    _logger.error(
        "send_reminders run failed",
        extra={"flow_run_id": str(getattr(flow_run, "id", "unknown")), "state": str(state)},
    )


@flow(name="send-reminders", on_failure=[report_failure])
def send_reminders() -> dict[str, int]:
    """Find every reminder due this hour and send it exactly once."""
    logger = get_run_logger()
    due = find_due_notifications()
    tally = send_due_notifications(due)
    logger.info("send_reminders complete: %s", tally)
    return tally


def main() -> None:
    """Serve both deployments until interrupted.

    ``hourly-send`` runs on a cron. ``preview-reminder`` has no schedule, so it
    only ever runs when triggered from the Prefect UI or CLI — it renders a real
    email for an event that is not due yet, which is the only way to check your
    work when the next genuine send is months away. ``send=False`` by default, so
    triggering it with stock parameters renders without touching Resend.
    """
    hourly = send_reminders.to_deployment(
        name="hourly-send",
        cron=HOURLY_CRON,
        description=(
            "Finds reminders due this hour and sends each exactly once. Per-user "
            "send_hour gating happens inside the flow, so the tick is a plain hourly cron."
        ),
    )
    preview = preview_reminder.to_deployment(
        name="preview-reminder",
        parameters={"days_before": DEFAULT_DAYS_BEFORE, "send": False},
        description=(
            "On-demand preview of a reminder email. Renders from real database rows and "
            "optionally sends via Resend, recording the result in test_email_log (never "
            "notification_log, which would suppress the genuine reminder)."
        ),
    )
    # `to_deployment` is overloaded for sync and async callers; both flows here are
    # sync, so these are RunnerDeployment objects rather than coroutines.
    serve(hourly, preview)  # type: ignore[arg-type]


if __name__ == "__main__":  # pragma: no cover - manual/long-running entrypoint
    import sys

    # `--once` runs the send exactly once and exits (local checks, cron fallback).
    # With no argument this serves the deployments and blocks, which is what the
    # worker container does.
    if "--once" in sys.argv:
        send_reminders()
    else:
        main()


__all__ = ["HOURLY_CRON", "main", "send_reminders"]
