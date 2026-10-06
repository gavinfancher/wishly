from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from wishly.schedule import due_occurrence, is_valid_month_day, occurrence_in_year

CHICAGO = ZoneInfo("America/Chicago")  # UTC-5 in October (daylight time)


def due(*, now: datetime, month: int = 10, day: int = 12, days_before: int = 7):
    """Mom's birthday, Oct 12, reminder at 8am Chicago time."""
    return due_occurrence(
        month=month, day=day, days_before=days_before, send_hour=8, tz=CHICAGO, now=now
    )


# --- the one-hour window ------------------------------------------------------


def test_due_at_send_hour() -> None:
    # 13:00 UTC is 8am in Chicago; Oct 5 + 7 days = Oct 12.
    assert due(now=datetime(2026, 10, 5, 13, 0, 4, tzinfo=UTC)) == date(2026, 10, 12)


def test_due_one_run_late() -> None:
    # The 8am run was missed; the 9am run still sends it.
    assert due(now=datetime(2026, 10, 5, 14, 0, 4, tzinfo=UTC)) == date(2026, 10, 12)


def test_not_due_two_runs_late() -> None:
    assert due(now=datetime(2026, 10, 5, 15, 0, 4, tzinfo=UTC)) is None


def test_not_due_early() -> None:
    assert due(now=datetime(2026, 10, 5, 12, 0, 4, tzinfo=UTC)) is None


def test_not_due_on_wrong_day() -> None:
    assert due(now=datetime(2026, 10, 6, 13, 0, 4, tzinfo=UTC)) is None


def test_day_of_reminder() -> None:
    assert due(now=datetime(2026, 10, 12, 13, 0, tzinfo=UTC), days_before=0) == date(2026, 10, 12)


# --- calendar edge cases --------------------------------------------------------


def test_reminder_crosses_year_boundary() -> None:
    # Jan 3 event, 7 days before = Dec 27 of the previous year (CST, UTC-6 in winter).
    now = datetime(2026, 12, 27, 14, 0, tzinfo=UTC)
    assert due(now=now, month=1, day=3) == date(2027, 1, 3)


@pytest.mark.parametrize(
    ("year", "expected"),
    [(2027, date(2027, 2, 28)), (2028, date(2028, 2, 29))],
)
def test_feb_29_falls_on_feb_28_in_non_leap_years(year: int, expected: date) -> None:
    assert occurrence_in_year(2, 29, year) == expected


@pytest.mark.parametrize(
    ("month", "day", "valid"),
    [(2, 29, True), (2, 30, False), (4, 31, False), (12, 31, True), (13, 1, False), (1, 0, False)],
)
def test_is_valid_month_day(month: int, day: int, valid: bool) -> None:
    assert is_valid_month_day(month, day) is valid
