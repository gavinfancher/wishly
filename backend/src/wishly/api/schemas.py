"""Pydantic request/response schemas with validation (PLAN §6, T3.1).

Validation rules enforced here (mirrored by the frontend per PLAN):

* ``event_type`` is one of ``birthday | anniversary | custom``.
* ``event_month`` 1–12; ``event_day`` valid for that month, with **Feb 29
  always allowed** (leap occasions observed on Feb 28 in non-leap years by the
  sender — see PLAN §7).
* ``days_before`` 0–365, unique per event (uniqueness enforced in the route).
* ``send_hour`` 0–23.
* ``timezone`` is a valid IANA name (validated via :mod:`zoneinfo`).
"""

from __future__ import annotations

import datetime as dt
import uuid
from enum import StrEnum
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Max real days in each month (index 0 unused); February uses 29 so leap-day
# birthdays/anniversaries are accepted regardless of year.
_MAX_DAY_IN_MONTH = (0, 31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


class EventType(StrEnum):
    """The kind of occasion being tracked."""

    birthday = "birthday"
    anniversary = "anniversary"
    custom = "custom"


def _validate_iana_timezone(value: str) -> str:
    """Return ``value`` if it is a loadable IANA timezone, else raise."""
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"'{value}' is not a valid IANA timezone.") from exc
    return value


def check_month_day(month: int, day: int) -> None:
    """Raise ``ValueError`` if ``day`` is out of range for ``month``."""
    if not 1 <= month <= 12:
        raise ValueError("event_month must be between 1 and 12.")
    max_day = _MAX_DAY_IN_MONTH[month]
    if not 1 <= day <= max_day:
        raise ValueError(f"event_day {day} is invalid for month {month} (max {max_day}).")


# --------------------------------------------------------------------------- #
# Users / preferences (/me)
# --------------------------------------------------------------------------- #
class UserOut(BaseModel):
    """The current user as returned by ``GET /me``."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    first_name: str | None = None
    last_name: str | None = None
    timezone: str
    send_hour: int
    # ``None`` until onboarding is completed; the client gates the onboarding
    # redirect on this rather than on browser storage.
    onboarded_at: dt.datetime | None = None
    created_at: dt.datetime
    updated_at: dt.datetime


class UserUpdate(BaseModel):
    """Body for ``PATCH /me`` — update onboarding preferences."""

    model_config = ConfigDict(extra="forbid")

    timezone: str | None = None
    send_hour: int | None = Field(default=None, ge=0, le=23)
    # Set true by the onboarding flow to stamp ``onboarded_at`` server-side.
    onboarded: bool | None = None

    @field_validator("timezone")
    @classmethod
    def _tz(cls, value: str | None) -> str | None:
        return None if value is None else _validate_iana_timezone(value)

    @model_validator(mode="after")
    def _at_least_one(self) -> UserUpdate:
        if self.timezone is None and self.send_hour is None and self.onboarded is None:
            raise ValueError("Provide at least one of 'timezone', 'send_hour', or 'onboarded'.")
        return self


# --------------------------------------------------------------------------- #
# Events
# --------------------------------------------------------------------------- #
class _EventBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    event_type: EventType
    event_month: int = Field(ge=1, le=12)
    event_day: int = Field(ge=1, le=31)
    event_year: int | None = Field(default=None, ge=1, le=9999)
    message: str | None = Field(default=None, max_length=2000)
    recipient_email: str | None = None
    recipient_name: str | None = None
    template_id: uuid.UUID | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def _valid_calendar_day(self) -> _EventBase:
        check_month_day(self.event_month, self.event_day)
        return self


class EventCreate(_EventBase):
    """Body for ``POST /events``."""

    model_config = ConfigDict(extra="forbid")


class EventUpdate(BaseModel):
    """Body for ``PATCH /events/{id}`` — every field optional (partial update)."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    event_type: EventType | None = None
    event_month: int | None = Field(default=None, ge=1, le=12)
    event_day: int | None = Field(default=None, ge=1, le=31)
    event_year: int | None = Field(default=None, ge=1, le=9999)
    message: str | None = Field(default=None, max_length=2000)
    recipient_email: str | None = None
    recipient_name: str | None = None
    template_id: uuid.UUID | None = None
    is_active: bool | None = None

    def updated_fields(self) -> dict[str, object]:
        """The subset of fields explicitly provided in the request body."""
        return self.model_dump(exclude_unset=True)


class EventOut(BaseModel):
    """An event as returned by the API (with its reminder lead times)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: str
    title: str
    event_type: str
    event_month: int
    event_day: int
    event_year: int | None
    message: str | None
    recipient_email: str | None
    recipient_name: str | None
    template_id: uuid.UUID | None
    is_active: bool
    created_at: dt.datetime
    updated_at: dt.datetime
    reminders: list[int] = Field(default_factory=list)

    @field_validator("reminders", mode="before")
    @classmethod
    def _reminder_days(cls, value: Any) -> Any:
        """Accept the ORM ``reminders`` relationship as well as a list of ints.

        ``model_validate(event)`` reads ``event.reminders``, which is a list of
        ``EventReminder`` rows — not the ``list[int]`` this field declares. Coercing
        here (rather than overwriting the attribute after validation) means every
        call site is correct by construction: validation happens before any
        post-assignment could run, so the old two-step raised before it could fix
        itself, and only for events that actually had reminders.
        """
        if isinstance(value, list) and value and not isinstance(value[0], int):
            return sorted(r.days_before for r in value)
        return value


# --------------------------------------------------------------------------- #
# Reminders
# --------------------------------------------------------------------------- #
class RemindersReplace(BaseModel):
    """Body for ``PUT /events/{id}/reminders`` — the full replacement set.

    ``days_before`` values must be unique; duplicates are rejected here so the
    DB unique constraint is never the first line of defence.
    """

    model_config = ConfigDict(extra="forbid")

    days_before: list[int] = Field(default_factory=list)

    @field_validator("days_before")
    @classmethod
    def _range_and_unique(cls, value: list[int]) -> list[int]:
        for d in value:
            if not 0 <= d <= 365:
                raise ValueError("each days_before must be between 0 and 365.")
        if len(set(value)) != len(value):
            raise ValueError("days_before values must be unique.")
        return value


class RemindersOut(BaseModel):
    """The reminder set for an event, sorted ascending."""

    event_id: uuid.UUID
    days_before: list[int]


class NotificationOut(BaseModel):
    """One row of the send log, flattened with the event it belongs to.

    ``status`` mirrors ``notification_log.status`` verbatim
    (``pending``/``sent``/``failed``/``skipped``) rather than translating it — the
    ledger is the source of truth for what happened, and a lossy rename in the API
    layer would make the UI disagree with the table you'd query when debugging.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_id: uuid.UUID
    event_title: str
    event_type: str
    days_before: int
    occurrence_date: dt.date
    status: str
    # Null for rows that never reached a successful send (pending/failed/skipped).
    sent_at: dt.datetime | None = None
    created_at: dt.datetime
