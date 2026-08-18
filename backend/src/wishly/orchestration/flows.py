"""Prefect flow for the hourly send pipeline (T5.4).

:func:`send_reminders` chains the two tasks in
:mod:`wishly.orchestration.tasks`: find what is due, then claim/send/record it.
The send task carries its own retry policy for transient Resend errors.

The schedule is a plain hourly tick — per-user ``send_hour`` gating happens
inside the task, so the flow does not need to know anything about timezones.
Cron and work pool live in ``backend/prefect.yaml``; deploy with::

    uv run prefect deploy --all

Run it once locally (no server or Cloud account needed)::

    uv run python -m wishly.orchestration.flows
"""

from __future__ import annotations

from prefect import flow, get_run_logger

from wishly.core.logging import get_logger
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


if __name__ == "__main__":  # pragma: no cover - manual local run
    send_reminders()


__all__ = ["HOURLY_CRON", "send_reminders"]
