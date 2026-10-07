from datetime import UTC, datetime

import psycopg
from fastapi.testclient import TestClient

from tests.conftest import RUN_TOKEN
from wishly.run import send_due_reminders

# 13:00 UTC on Oct 5 is 8am in Chicago: 7 days before Mom's birthday (Oct 12).
SEND_TIME = datetime(2026, 10, 5, 13, 0, 3, tzinfo=UTC)


def add_mom_reminder(db: psycopg.Connection, *, onboarded: bool = True) -> None:
    user_id = db.execute(
        """
        insert into users (email, password_hash, timezone, send_hour, onboarded_at)
        values ('me@example.com', 'unused', 'America/Chicago', 8, %s)
        returning id
        """,
        (datetime.now(UTC) if onboarded else None,),
    ).fetchone()["id"]
    db.execute(
        """
        insert into reminders (user_id, title, month, day, days_before)
        values (%s, 'Mom''s birthday', 10, 12, '{7,0}')
        """,
        (user_id,),
    )


def test_sends_a_due_reminder(db: psycopg.Connection) -> None:
    add_mom_reminder(db)
    emails = []

    result = send_due_reminders(db, lambda **e: emails.append(e), now=SEND_TIME)

    assert result == {"sent": 1, "failed": 0}
    assert emails[0]["to"] == "me@example.com"
    assert emails[0]["subject"] == "In 7 days: Mom's birthday"
    assert "October 12" in emails[0]["text"]


def test_running_twice_sends_once(db: psycopg.Connection) -> None:
    add_mom_reminder(db)
    emails = []
    send = lambda **e: emails.append(e)  # noqa: E731

    send_due_reminders(db, send, now=SEND_TIME)
    send_due_reminders(db, send, now=SEND_TIME)  # e.g. EventBridge retried

    assert len(emails) == 1


def test_failed_send_is_retried_next_run(db: psycopg.Connection) -> None:
    add_mom_reminder(db)

    def broken(**_: str) -> None:
        raise RuntimeError("Resend is down")

    assert send_due_reminders(db, broken, now=SEND_TIME) == {"sent": 0, "failed": 1}

    emails = []
    later = SEND_TIME.replace(hour=14)  # one hour late: still inside the window
    assert send_due_reminders(db, lambda **e: emails.append(e), now=later)["sent"] == 1


def test_users_who_havent_onboarded_get_nothing(db: psycopg.Connection) -> None:
    add_mom_reminder(db, onboarded=False)

    assert send_due_reminders(db, lambda **e: None, now=SEND_TIME)["sent"] == 0


def test_run_endpoint_requires_the_run_token(client: TestClient) -> None:
    assert client.post("/internal/run").status_code == 401  # a user's token
    ok = client.post("/internal/run", headers={"Authorization": f"Bearer {RUN_TOKEN}"})
    assert ok.status_code == 200


def test_run_deletes_expired_sessions(db: psycopg.Connection) -> None:
    user_id = db.execute(
        "insert into users (email, password_hash) values ('x@example.com', 'unused') returning id"
    ).fetchone()["id"]
    db.execute(
        """
        insert into sessions (token_hash, user_id, expires_at) values
            ('old', %(id)s, now() - interval '1 day'),
            ('current', %(id)s, now() + interval '1 day')
        """,
        {"id": user_id},
    )

    send_due_reminders(db, lambda **e: None, now=datetime.now(UTC))

    rows = db.execute("select token_hash from sessions").fetchall()
    assert [row["token_hash"] for row in rows] == ["current"]
