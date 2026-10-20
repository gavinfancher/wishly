from datetime import UTC, date, datetime

import pytest

from wishly.schedule import due_occurrence, is_valid_month_day, occurrence_in_year

# October is daylight time in New York (UTC-4), so 9am Eastern is 13:00 UTC.


def due(*, now: datetime, month: int = 10, day: int = 12, days_before: int = 7):
    """Mom's birthday, Oct 12, reminder 7 days before."""
    return due_occurrence(month=month, day=day, days_before=days_before, now=now)


# --- the 9am Eastern send ---------------------------------------------------------


def test_due_at_9am_eastern() -> None:
    # Oct 5 + 7 days = Oct 12.
    assert due(now=datetime(2026, 10, 5, 13, 0, 4, tzinfo=UTC)) == date(2026, 10, 12)


def test_not_due_before_9am_eastern() -> None:
    assert due(now=datetime(2026, 10, 5, 12, 59, tzinfo=UTC)) is None


def test_still_due_later_the_same_day() -> None:
    # 11:45pm Eastern: a missed 9am run is caught up before the day ends.
    assert due(now=datetime(2026, 10, 6, 3, 45, tzinfo=UTC)) == date(2026, 10, 12)


def test_not_due_the_next_day() -> None:
    # 9am Eastern on Oct 6 is 6 days before, not 7.
    assert due(now=datetime(2026, 10, 6, 13, 0, tzinfo=UTC)) is None


def test_day_of_reminder() -> None:
    assert due(now=datetime(2026, 10, 12, 13, 0, tzinfo=UTC), days_before=0) == date(2026, 10, 12)


def test_9am_eastern_in_winter() -> None:
    # Standard time (UTC-5): 9am Eastern is 14:00 UTC, so 13:00 UTC is too early.
    jan = {"month": 1, "day": 10, "days_before": 0}
    assert due(now=datetime(2027, 1, 10, 13, 0, tzinfo=UTC), **jan) is None
    assert due(now=datetime(2027, 1, 10, 14, 0, tzinfo=UTC), **jan) == date(2027, 1, 10)


# --- calendar edge cases --------------------------------------------------------


def test_reminder_crosses_year_boundary() -> None:
    # Jan 3 event, 7 days before = Dec 27 of the previous year.
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
