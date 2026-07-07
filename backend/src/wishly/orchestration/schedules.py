"""Job, hourly schedule, and run-failure alerting for the send pipeline (T5.4).

* :data:`send_reminders_job` wires :func:`find_due_notifications` into
  :func:`send_due_notifications` (the send op carries its own retry policy for
  transient Resend errors — see :data:`wishly.orchestration.ops.SEND_RETRY_POLICY`).
* :data:`hourly_send_schedule` triggers the job at the top of every hour; the
  per-user ``send_hour`` gating happens inside the op, so the schedule itself is
  a plain hourly tick.
* :func:`send_failure_alert` is a run-failure sensor that logs/alerts when a run
  of the job fails (after the op exhausted its retries).
"""

from __future__ import annotations

from dagster import (
    DefaultScheduleStatus,
    RunFailureSensorContext,
    ScheduleDefinition,
    job,
    run_failure_sensor,
)

from wishly.core.logging import get_logger
from wishly.orchestration.ops import find_due_notifications, send_due_notifications

# Hourly tick. Per-user send-window gating (local hour == send_hour) is applied
# inside the op, so the schedule only needs to fire once per hour.
HOURLY_CRON = "0 * * * *"

_logger = get_logger("wishly.orchestration")


@job
def send_reminders_job() -> None:
    """Find the reminders due this hour and send them, idempotently."""
    send_due_notifications(find_due_notifications())


hourly_send_schedule = ScheduleDefinition(
    name="hourly_send_schedule",
    job=send_reminders_job,
    cron_schedule=HOURLY_CRON,
    # Default to STOPPED so it is explicitly enabled in the UI per environment;
    # the schedule appears and is enable-able exactly as the acceptance asks.
    default_status=DefaultScheduleStatus.STOPPED,
    execution_timezone="UTC",
)


@run_failure_sensor(monitored_jobs=[send_reminders_job])
def send_failure_alert(context: RunFailureSensorContext) -> None:
    """Log/alert when a send run fails (post-retry).

    Hooks into Dagster's failure path so an exhausted-retry failure surfaces in
    structured logs (and is the single place to wire paging/Slack later). Kept
    side-effect-light so it never itself raises and masks the original failure.
    """
    run = context.dagster_run
    _logger.error(
        "send_reminders_job run failed",
        extra={
            "run_id": run.run_id,
            "job_name": run.job_name,
            "failure": context.failure_event.message,
        },
    )


__all__ = [
    "HOURLY_CRON",
    "hourly_send_schedule",
    "send_failure_alert",
    "send_reminders_job",
]
