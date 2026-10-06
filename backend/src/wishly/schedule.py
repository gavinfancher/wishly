"""When is a reminder due? Pure date math — no database, no clock, no I/O.

Callers pass in `now`, so every rule here is testable at any instant we like.
"""

import calendar
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo


def is_valid_month_day(month: int, day: int) -> bool:
    """Can this date ever happen? Feb 29 yes (leap years), Apr 31 no."""
    if not 1 <= month <= 12:
        return False
    # 2000 is a leap year, so February allows 29 here.
    return 1 <= day <= calendar.monthrange(2000, month)[1]


def occurrence_in_year(month: int, day: int, year: int) -> date:
    """The date an event falls on in a given year. Feb 29 → Feb 28 in non-leap years."""
    if month == 2 and day == 29 and not calendar.isleap(year):
        return date(year, 2, 28)
    return date(year, month, day)


def due_occurrence(
    *,
    month: int,
    day: int,
    days_before: int,
    send_hour: int,
    tz: ZoneInfo,
    now: datetime,
) -> date | None:
    """If this reminder should go out in the run happening at `now`, return
    the occurrence date it's for. Otherwise None.

    A reminder's send moment is `send_hour` local time, `days_before` days
    before the event. It's due if that moment is in this hour or the previous
    one: on time, or at most one missed run late.

    The returned date is part of notification_log's unique key, so it's what
    stops the same reminder going out twice.
    """
    this_hour = now.astimezone(UTC).replace(minute=0, second=0, microsecond=0)

    # Step back through the window in UTC, then convert to local time. Doing the
    # subtraction in UTC keeps it correct across daylight-saving changes.
    for hour in (this_hour, this_hour - timedelta(hours=1)):
        local = hour.astimezone(tz)
        if local.hour != send_hour:
            continue

        occurrence = local.date() + timedelta(days=days_before)
        if occurrence_in_year(month, day, occurrence.year) == occurrence:
            return occurrence

    return None
