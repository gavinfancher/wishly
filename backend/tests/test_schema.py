import psycopg

from tests.conftest import SCHEMA_SQL


def test_schema_has_every_table(db: psycopg.Connection) -> None:
    rows = db.execute(
        "select table_name from information_schema.tables where table_schema = 'public'"
    ).fetchall()

    assert {row["table_name"] for row in rows} == {"users", "reminders", "sends"}


def test_schema_is_safe_to_rerun(db: psycopg.Connection) -> None:
    # The session fixture already applied it once.
    db.execute(SCHEMA_SQL.read_text())


def test_sends_rejects_a_second_claim(db: psycopg.Connection) -> None:
    """The whole duplicate-email defence, in one test."""
    db.execute("insert into users (id, email) values ('u1', 'a@example.com')")
    reminder = db.execute(
        """
        insert into reminders (user_id, title, month, day, days_before)
        values ('u1', 'Mom', 10, 12, '{7}') returning id
        """
    ).fetchone()

    claim = """
        insert into sends (reminder_id, days_before, occurrence_date)
        values (%s, 7, '2026-10-12') on conflict do nothing
    """
    assert db.execute(claim, (reminder["id"],)).rowcount == 1  # first run wins
    assert db.execute(claim, (reminder["id"],)).rowcount == 0  # second run gets nothing
