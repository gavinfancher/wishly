"""Pure send-window / due-date logic for the send pipeline (PLAN §7 steps 1-3).

Kept free of the web layer and the database so the riskiest logic in the app —
timezone windowing, ``send_hour`` gating, year-boundary reminders, and the
Feb 29 -> Feb 28 rule — is unit-testable in isolation.

All instants and dates flow through :mod:`pendulum`: it is the project's single
time library, so DST-aware conversion, date arithmetic, and leap-year checks all
come from one place instead of being split across ``datetime``/``zoneinfo``.

The matching strategy is **additive**: for a given local ``today`` and a lead
time ``days_before``, compute ``target = today + days_before`` and check whether
``target`` lands on the event's month/day. Adding the lead time (rather than
subtracting it from the occurrence) makes year-boundary reminders fall out for
free — a 30-day reminder evaluated in December naturally targets a January
occurrence.
"""

from __future__ import annotations

import datetime

import pendulum
from pendulum.tz.exceptions import InvalidTimezone


def _zone(timezone: str) -> pendulum.Timezone:
    """Resolve an IANA name, falling back to UTC.

    An unknown name can't be allowed to crash a run: one bad row would stop
    every other user's reminders for that hour.
    """
    try:
        return pendulum.timezone(timezone)
    except (InvalidTimezone, ValueError):
        return pendulum.UTC


def local_now(now_utc: datetime.datetime, timezone: str) -> pendulum.DateTime:
    """Convert an aware UTC instant to the user's local wall-clock time.

    DST is handled by pendulum's zone conversion — no manual offset math.

    Args:
        now_utc: A timezone-aware instant (assumed UTC if naive).
        timezone: An IANA timezone name, e.g. ``"America/New_York"``.
    """
    instant = pendulum.instance(now_utc, tz="UTC") if now_utc.tzinfo is None else now_utc
    return pendulum.instance(instant).in_timezone(_zone(timezone))


def is_in_send_window(now_utc: datetime.datetime, timezone: str, send_hour: int) -> bool:
    """Whether ``now_utc`` falls in the user's send window for this hourly run.

    True iff the user's **local hour equals ``send_hour``** (PLAN §7 step 1).
    """
    return local_now(now_utc, timezone).hour == send_hour


def local_today(now_utc: datetime.datetime, timezone: str) -> pendulum.Date:
    """The user's local calendar date for ``now_utc`` (PLAN §7 step 2)."""
    return local_now(now_utc, timezone).date()


def occurrence_on(
    today: datetime.date,
    days_before: int,
    event_month: int,
    event_day: int,
) -> pendulum.Date | None:
    """Return the occurrence date if a reminder is due, else ``None`` (step 3).

    A reminder with lead time ``days_before`` is due when ``today + days_before``
    lands on the event's ``(month, day)``. The Feb 29 rule is encoded here: in a
    **non-leap** target year, a Feb 29 event is observed on **Feb 28**, so a
    ``target`` of Feb 28 in such a year matches a ``(2, 29)`` event.

    Args:
        today: The user's local date.
        days_before: Lead time in days (``0`` = day-of).
        event_month: The event's month (1-12).
        event_day: The event's day (1-31; may be 29 for a Feb-29 event).

    Returns:
        ``target`` (= ``today + days_before``) when due, otherwise ``None``.
    """
    target = pendulum.date(today.year, today.month, today.day).add(days=days_before)

    # Exact month/day match (the common case, including a real Feb 29 in a leap
    # target year).
    if (target.month, target.day) == (event_month, event_day):
        return target

    # Feb 29 event observed on Feb 28 in a non-leap target year.
    if (
        (event_month, event_day) == (2, 29)
        and (target.month, target.day) == (2, 28)
        and not target.is_leap_year()
    ):
        return target

    return None


__all__ = [
    "is_in_send_window",
    "local_now",
    "local_today",
    "occurrence_on",
]
