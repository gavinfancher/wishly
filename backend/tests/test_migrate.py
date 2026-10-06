import psycopg

from wishly.migrate import migrate


def test_rerunning_migrations_is_a_no_op(db: psycopg.Connection) -> None:
    # The session fixture already migrated this database.
    assert migrate(db) == []


def test_schema_has_every_table(db: psycopg.Connection) -> None:
    rows = db.execute(
        "select table_name from information_schema.tables where table_schema = 'public'"
    ).fetchall()

    assert {row["table_name"] for row in rows} == {
        "schema_migrations",
        "users",
        "reminders",
        "sends",
    }
