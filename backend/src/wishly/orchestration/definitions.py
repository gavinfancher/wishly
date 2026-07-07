"""Dagster code location for Wishly's send pipeline (T5.1 + T5.4).

This module exposes the top-level :data:`defs` (:class:`dagster.Definitions`)
that Dagster loads: the send job, its hourly schedule, the run-failure alert
sensor, and the shared resources (sync DB session + Resend client).

Load it with::

    dagster dev -m wishly.orchestration.definitions

or validate it with::

    dagster definitions validate -m wishly.orchestration.definitions
"""

from __future__ import annotations

from dagster import Definitions

from wishly.orchestration.resources import DatabaseResource, ResendResource
from wishly.orchestration.schedules import (
    hourly_send_schedule,
    send_failure_alert,
    send_reminders_job,
)

defs = Definitions(
    jobs=[send_reminders_job],
    schedules=[hourly_send_schedule],
    sensors=[send_failure_alert],
    resources={
        "database": DatabaseResource(),
        "resend": ResendResource(),
    },
)

__all__ = ["defs"]
