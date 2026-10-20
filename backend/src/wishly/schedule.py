"""When is a reminder due? Pure date math — no database, no clock, no I/O.

Callers pass in `now`, so every rule here is testable at any instant we like.
"""

import calendar
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

# Everyone's reminders go out at 9am Eastern. Users' own timezone and send_hour
# are still stored (the frontend sets them) but no longer change delivery.
SEND_TZ = ZoneInfo("America/New_York")
SEND_HOUR = 9


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


def due_occurrence(*, month: int, day: int, days_before: int, now: datetime) -> date | None:
    """If this reminder should go out at `now`, return the occurrence date it's
    for. Otherwise None.

    A reminder is due from 9:00 Eastern, `days_before` days before the event,
    until midnight Eastern that day. The scheduler's 9:00 run sends it; if that
    run was missed (the app was restarting) or the send failed, any later run
    the same day still does.

    The returned date is part of the `sends` primary key, so it's what stops
    the same reminder going out twice.
    """
    local = now.astimezone(SEND_TZ)
    if local.hour < SEND_HOUR:
        return None

    occurrence = local.date() + timedelta(days=days_before)
    if occurrence_in_year(month, day, occurrence.year) == occurrence:
        return occurrence
    return None
