"""Tests for the manually-triggered preview flow (wishly.orchestration.preview).

Covers the two pieces with real logic: the next-occurrence calculation (which
must agree with the Feb 29 rule the real sender uses) and target resolution,
including the refusals that stop a preview emailing the wrong person.
"""

from __future__ import annotations

import datetime

import pytest

from wishly.db.models import Event, User
from wishly.orchestration.preview import PreviewError, next_occurrence, resolve_target


def _user(session, email: str, **kw) -> User:
    user = User(
        id=kw.pop("id", f"user_{email.split('@')[0]}"),
        email=email,
        first_name=kw.pop("first_name", "Gavin"),
        timezone=kw.pop("timezone", "America/Chicago"),
        send_hour=kw.pop("send_hour", 8),
        **kw,
    )
    session.add(user)
    session.flush()
    return user


def _event(session, user: User, **kw) -> Event:
    event = Event(
        user_id=user.id,
        title=kw.pop("title", "Mom's Bday"),
        event_type=kw.pop("event_type", "birthday"),
        event_month=kw.pop("event_month", 4),
        event_day=kw.pop("event_day", 3),
        **kw,
    )
    session.add(event)
    session.flush()
    return event


class TestNextOccurrence:
    def test_later_this_year(self) -> None:
        assert next_occurrence(datetime.date(2026, 1, 10), 4, 3) == datetime.date(2026, 4, 3)

    def test_today_counts_as_next(self) -> None:
        assert next_occurrence(datetime.date(2026, 4, 3), 4, 3) == datetime.date(2026, 4, 3)

    def test_rolls_to_next_year_once_passed(self) -> None:
        # The real complaint that motivated this flow: an event months in the
        # past must still render, not return None the way occurrence_on does.
        assert next_occurrence(datetime.date(2026, 8, 23), 4, 3) == datetime.date(2027, 4, 3)

    def test_feb_29_observed_on_feb_28_in_non_leap_year(self) -> None:
        # Same rule as due.occurrence_on; 2027 is not a leap year.
        assert next_occurrence(datetime.date(2027, 1, 1), 2, 29) == datetime.date(2027, 2, 28)

    def test_feb_29_kept_in_leap_year(self) -> None:
        assert next_occurrence(datetime.date(2028, 1, 1), 2, 29) == datetime.date(2028, 2, 29)


class TestResolveTarget:
    def test_defaults_to_the_only_user_and_oldest_event(self, sync_session) -> None:
        user = _user(sync_session, "solo@example.com")
        first = _event(sync_session, user, title="First")
        _event(sync_session, user, title="Second")

        target = resolve_target(sync_session, user_email=None, event_id=None)

        assert target.user_email == "solo@example.com"
        assert target.event_id == str(first.id)
        assert target.title == "First"

    def test_refuses_to_guess_between_multiple_users(self, sync_session) -> None:
        a = _user(sync_session, "a@example.com", id="user_a")
        _user(sync_session, "b@example.com", id="user_b")
        _event(sync_session, a)

        # Guessing would email a real person who never asked for it.
        with pytest.raises(PreviewError, match="pass user_email"):
            resolve_target(sync_session, user_email=None, event_id=None)

    def test_selects_the_named_user(self, sync_session) -> None:
        _user(sync_session, "a@example.com", id="user_a")
        b = _user(sync_session, "b@example.com", id="user_b")
        _event(sync_session, b, title="B's event")

        target = resolve_target(sync_session, user_email="b@example.com", event_id=None)
        assert target.title == "B's event"

    def test_ignores_inactive_events(self, sync_session) -> None:
        user = _user(sync_session, "solo@example.com")
        _event(sync_session, user, title="Archived", is_active=False)

        with pytest.raises(PreviewError, match="no active events"):
            resolve_target(sync_session, user_email=None, event_id=None)

    def test_ignores_soft_deleted_users(self, sync_session) -> None:
        _user(
            sync_session,
            "gone@example.com",
            deleted_at=datetime.datetime.now(tz=datetime.UTC),
        )

        with pytest.raises(PreviewError, match="no active users"):
            resolve_target(sync_session, user_email=None, event_id=None)

    def test_unknown_event_id_is_an_error_not_a_silent_fallback(self, sync_session) -> None:
        user = _user(sync_session, "solo@example.com")
        _event(sync_session, user)
        other = "00000000-0000-0000-0000-000000000000"

        with pytest.raises(PreviewError, match="no active event with id"):
            resolve_target(sync_session, user_email=None, event_id=other)

    def test_carries_recipient_overrides_through(self, sync_session) -> None:
        user = _user(sync_session, "solo@example.com")
        _event(
            sync_session,
            user,
            recipient_email="other@example.com",
            recipient_name="Someone Else",
        )

        target = resolve_target(sync_session, user_email=None, event_id=None)
        assert target.recipient_email == "other@example.com"
        assert target.recipient_name == "Someone Else"
