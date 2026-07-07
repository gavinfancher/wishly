"""Unit tests for send-window / due-date logic (PLAN T5.2, §7 steps 1-3)."""

from __future__ import annotations

import datetime

import pytest

from wishly.orchestration.due import (
    is_in_send_window,
    local_now,
    local_today,
    occurrence_on,
)


# --- local_now / send window ------------------------------------------------- #
def test_local_now_converts_utc_to_eastern() -> None:
    # 2026-06-13 14:00 UTC → 10:00 EDT (America/New_York is UTC-4 in June).
    now_utc = datetime.datetime(2026, 6, 13, 14, 0, tzinfo=datetime.UTC)
    local = local_now(now_utc, "America/New_York")
    assert local.hour == 10
    assert local.tzinfo is not None


def test_local_now_unknown_timezone_falls_back_to_utc() -> None:
    now_utc = datetime.datetime(2026, 6, 13, 8, 0, tzinfo=datetime.UTC)
    local = local_now(now_utc, "Mars/Phobos")
    assert local.hour == 8


@pytest.mark.parametrize(
    ("now_utc", "timezone", "send_hour", "expected"),
    [
        # 13:00 UTC = 08:00 CDT (America/Chicago, UTC-5) on a summer day.
        (datetime.datetime(2026, 6, 13, 13, 0, tzinfo=datetime.UTC), "America/Chicago", 8, True),
        (datetime.datetime(2026, 6, 13, 14, 0, tzinfo=datetime.UTC), "America/Chicago", 8, False),
        # Midnight UTC is hour 0 in UTC.
        (datetime.datetime(2026, 1, 15, 0, 0, tzinfo=datetime.UTC), "UTC", 0, True),
        (datetime.datetime(2026, 1, 15, 0, 0, tzinfo=datetime.UTC), "UTC", 8, False),
    ],
)
def test_is_in_send_window(
    now_utc: datetime.datetime,
    timezone: str,
    send_hour: int,
    expected: bool,
) -> None:
    assert is_in_send_window(now_utc, timezone, send_hour) is expected


def test_local_today_respects_timezone() -> None:
    # 2026-01-01 05:00 UTC is still 2025-12-31 in US Pacific.
    now_utc = datetime.datetime(2026, 1, 1, 5, 0, tzinfo=datetime.UTC)
    assert local_today(now_utc, "America/Los_Angeles") == datetime.date(2025, 12, 31)


# --- occurrence_on --------------------------------------------------------- #
def test_occurrence_on_exact_match() -> None:
    today = datetime.date(2026, 6, 6)
    # 7-day lead: target = Jun 13 → matches a Jun 13 birthday.
    result = occurrence_on(today, days_before=7, event_month=6, event_day=13)
    assert result == datetime.date(2026, 6, 13)


def test_occurrence_on_no_match() -> None:
    today = datetime.date(2026, 6, 6)
    assert occurrence_on(today, days_before=7, event_month=6, event_day=14) is None


def test_occurrence_on_day_of_reminder() -> None:
    today = datetime.date(2026, 3, 15)
    result = occurrence_on(today, days_before=0, event_month=3, event_day=15)
    assert result == datetime.date(2026, 3, 15)


def test_occurrence_on_year_boundary_december_to_january() -> None:
    # 30-day reminder evaluated Dec 2 → target Jan 1 → matches a Jan 1 event.
    today = datetime.date(2025, 12, 2)
    result = occurrence_on(today, days_before=30, event_month=1, event_day=1)
    assert result == datetime.date(2026, 1, 1)


def test_occurrence_on_feb_29_in_leap_year() -> None:
    # 2028 is a leap year; Feb 29 event matches exactly on Feb 29.
    today = datetime.date(2028, 2, 20)
    result = occurrence_on(today, days_before=9, event_month=2, event_day=29)
    assert result == datetime.date(2028, 2, 29)


def test_occurrence_on_feb_29_observed_on_feb_28_non_leap_year() -> None:
    # 2026 is not a leap year; a Feb 29 event is observed on Feb 28.
    today = datetime.date(2026, 2, 20)
    result = occurrence_on(today, days_before=8, event_month=2, event_day=29)
    assert result == datetime.date(2026, 2, 28)


def test_occurrence_on_feb_29_no_false_match_on_feb_27() -> None:
    today = datetime.date(2026, 2, 19)
    assert occurrence_on(today, days_before=8, event_month=2, event_day=29) is None
