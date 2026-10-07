"""The browser-facing API: /v1/me and /v1/reminders.

Every query is scoped by user_id = the caller, so nobody can read or change
another user's reminders. Someone else's reminder ID gets a 404, not a 403,
so we never confirm that it exists.
"""

from datetime import datetime
from typing import Annotated
from zoneinfo import available_timezones

from fastapi import APIRouter, Depends, HTTPException, Response
from psycopg import Connection
from pydantic import BaseModel, Field, field_validator, model_validator

from wishly.auth import CurrentUser, User
from wishly.db import get_conn
from wishly.schedule import is_valid_month_day

router = APIRouter(prefix="/v1")
Conn = Annotated[Connection, Depends(get_conn)]

TIMEZONES = available_timezones()


# --- shapes of request and response bodies -------------------------------------


class UserUpdate(BaseModel):
    timezone: str | None = None
    send_hour: int | None = Field(default=None, ge=0, le=23)
    # Onboarding sends true once; the server records when.
    onboarded: bool = False

    @field_validator("timezone")
    @classmethod
    def known_timezone(cls, value: str | None) -> str | None:
        if value is not None and value not in TIMEZONES:
            raise ValueError("unknown timezone")
        return value


class ReminderIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    month: int
    day: int
    # How many days before the date to email, e.g. [7, 1, 0].
    days_before: list[Annotated[int, Field(ge=0, le=365)]] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def check(self) -> ReminderIn:
        if not is_valid_month_day(self.month, self.day):
            raise ValueError("that date doesn't exist")
        # Drop duplicates; furthest-out first.
        self.days_before = sorted(set(self.days_before), reverse=True)
        return self


class Reminder(ReminderIn):
    id: int
    created_at: datetime


# --- /v1/me ----------------------------------------------------------------------


@router.get("/me")
def get_me(user: CurrentUser) -> User:
    return User(**user)


@router.patch("/me")
def update_me(body: UserUpdate, user: CurrentUser, conn: Conn) -> User:
    # coalesce(new, old): a field left out of the request keeps its value.
    row = conn.execute(
        """
        update users set
            timezone     = coalesce(%(timezone)s, timezone),
            send_hour    = coalesce(%(send_hour)s, send_hour),
            onboarded_at = case when %(onboarded)s then coalesce(onboarded_at, now())
                                else onboarded_at end
        where id = %(id)s
        returning *
        """,
        {**body.model_dump(), "id": user["id"]},
    ).fetchone()
    return User(**row)


# --- /v1/reminders -----------------------------------------------------------------
# `select *` / `returning *` is fine here: the response model keeps only its own
# fields, so columns like user_id never reach the browser.


@router.get("/reminders")
def list_reminders(user: CurrentUser, conn: Conn) -> list[Reminder]:
    rows = conn.execute(
        "select * from reminders where user_id = %s order by month, day",
        (user["id"],),
    ).fetchall()
    return [Reminder(**row) for row in rows]


@router.post("/reminders", status_code=201)
def create_reminder(body: ReminderIn, user: CurrentUser, conn: Conn) -> Reminder:
    row = conn.execute(
        """
        insert into reminders (user_id, title, month, day, days_before)
        values (%(user_id)s, %(title)s, %(month)s, %(day)s, %(days_before)s)
        returning *
        """,
        {**body.model_dump(), "user_id": user["id"]},
    ).fetchone()
    return Reminder(**row)


@router.put("/reminders/{reminder_id}")
def replace_reminder(reminder_id: int, body: ReminderIn, user: CurrentUser, conn: Conn) -> Reminder:
    row = conn.execute(
        """
        update reminders
        set title = %(title)s, month = %(month)s, day = %(day)s, days_before = %(days_before)s
        where id = %(id)s and user_id = %(user_id)s
        returning *
        """,
        {**body.model_dump(), "id": reminder_id, "user_id": user["id"]},
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="reminder not found")
    return Reminder(**row)


@router.delete("/reminders/{reminder_id}", status_code=204)
def delete_reminder(reminder_id: int, user: CurrentUser, conn: Conn) -> Response:
    deleted = conn.execute(
        "delete from reminders where id = %s and user_id = %s",
        (reminder_id, user["id"]),
    ).rowcount
    if deleted == 0:
        raise HTTPException(status_code=404, detail="reminder not found")
    return Response(status_code=204)
