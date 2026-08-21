"""SQLAlchemy 2.0 ORM models for every table in ``docs/PLAN.md`` §6.

Schema changes ship as Alembic migrations only (never hand-edited DDL). UUID
primary keys default to ``gen_random_uuid()`` which requires the ``pgcrypto``
extension — enabled in the initial migration.
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wishly.db.base import Base

# Reusable server-side default expressions.
_NOW = text("now()")
_GEN_UUID = text("gen_random_uuid()")


def _uuid_pk() -> Mapped[uuid.UUID]:
    """A UUID primary key column defaulted server-side via ``gen_random_uuid()``."""
    return mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=_GEN_UUID,
    )


def _created_at() -> Mapped[datetime.datetime]:
    """A non-null ``created_at timestamptz`` defaulting to ``now()``."""
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=_NOW)


def _updated_at() -> Mapped[datetime.datetime]:
    """A non-null ``updated_at timestamptz`` defaulting to ``now()`` (and on update)."""
    return mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=_NOW,
        onupdate=_NOW,
    )


class User(Base):
    """A signed-in app user, synced from Clerk; the source of truth for sending."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(Text, primary_key=True)  # Clerk user id (user_...)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    first_name: Mapped[str | None] = mapped_column(Text)
    last_name: Mapped[str | None] = mapped_column(Text)
    timezone: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'UTC'"))
    send_hour: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("8"))
    # Stamped when the user finishes onboarding. Nullable *because* absence is the
    # signal: ``timezone`` and ``send_hour`` both carry server defaults, so they
    # cannot distinguish "never onboarded" from "deliberately chose UTC at 08:00".
    onboarded_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime.datetime] = _created_at()
    updated_at: Mapped[datetime.datetime] = _updated_at()

    events: Mapped[list[Event]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    templates: Mapped[list[Template]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (CheckConstraint("send_hour between 0 and 23", name="send_hour_range"),)


class Event(Base):
    """An occasion a user tracks (birthday / anniversary / custom)."""

    __tablename__ = "events"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)  # birthday|anniversary|custom
    event_month: Mapped[int] = mapped_column(Integer, nullable=False)
    event_day: Mapped[int] = mapped_column(Integer, nullable=False)
    event_year: Mapped[int | None] = mapped_column(Integer)  # optional origin year -> "Nth"
    message: Mapped[str | None] = mapped_column(Text)
    recipient_email: Mapped[str | None] = mapped_column(Text)  # null = send to account owner
    recipient_name: Mapped[str | None] = mapped_column(Text)  # null = use owner's name
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("templates.id")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime.datetime] = _created_at()
    updated_at: Mapped[datetime.datetime] = _updated_at()

    user: Mapped[User] = relationship(back_populates="events")
    template: Mapped[Template | None] = relationship(back_populates="events")
    reminders: Mapped[list[EventReminder]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    notifications: Mapped[list[NotificationLog]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        CheckConstraint("event_month between 1 and 12", name="event_month_range"),
        CheckConstraint("event_day between 1 and 31", name="event_day_range"),
        Index("events_user_id_idx", "user_id"),
        Index(
            "events_month_day_idx",
            "event_month",
            "event_day",
            postgresql_where=text("is_active"),
        ),
    )


class EventReminder(Base):
    """A per-event lead time (e.g. 30, 7, 1, 0 days before)."""

    __tablename__ = "event_reminders"

    id: Mapped[uuid.UUID] = _uuid_pk()
    event_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
    )
    days_before: Mapped[int] = mapped_column(Integer, nullable=False)

    event: Mapped[Event] = relationship(back_populates="reminders")

    __table_args__ = (
        CheckConstraint("days_before between 0 and 365", name="days_before_range"),
        UniqueConstraint("event_id", "days_before", name="event_id_days_before"),
    )


class Template(Base):
    """A system or user-customized email template (Jinja2 source)."""

    __tablename__ = "templates"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("users.id", ondelete="CASCADE")
    )  # null = system template
    name: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)  # Jinja2 source
    html: Mapped[str] = mapped_column(Text, nullable=False)  # Jinja2 source (HTML)
    created_at: Mapped[datetime.datetime] = _created_at()

    user: Mapped[User | None] = relationship(back_populates="templates")
    events: Mapped[list[Event]] = relationship(back_populates="template")


class NotificationLog(Base):
    """The idempotency ledger that makes double-sends structurally impossible.

    The sender never sends without first winning an
    ``insert ... on conflict (event_id, days_before, occurrence_date) do nothing``.
    """

    __tablename__ = "notification_log"

    id: Mapped[uuid.UUID] = _uuid_pk()
    event_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
    )
    days_before: Mapped[int] = mapped_column(Integer, nullable=False)
    occurrence_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'pending'")
    )  # pending|sent|failed|skipped
    resend_id: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = _created_at()
    sent_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))

    event: Mapped[Event] = relationship(back_populates="notifications")

    __table_args__ = (
        UniqueConstraint(
            "event_id",
            "days_before",
            "occurrence_date",
            name="event_id_days_before_occurrence_date",
        ),
    )


class Suppression(Base):
    """Suppression list, fed by Resend bounce/complaint webhooks."""

    __tablename__ = "suppressions"

    email: Mapped[str] = mapped_column(Text, primary_key=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)  # bounce|complaint|manual
    created_at: Mapped[datetime.datetime] = _created_at()


__all__ = [
    "Base",
    "Event",
    "EventReminder",
    "NotificationLog",
    "Suppression",
    "Template",
    "User",
]
