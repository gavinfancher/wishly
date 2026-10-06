"""Apply the SQL files in migrations/ that this database hasn't seen yet.

    python -m wishly.migrate

Run once per deploy, before the new version starts. Safe to re-run: files
already applied are skipped.
"""

from pathlib import Path

import psycopg
from psycopg.rows import tuple_row

from wishly.settings import Settings

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

# Any constant works; it just has to be the same number every time.
MIGRATION_LOCK_ID = 7_140_001


def migrate(conn: psycopg.Connection) -> list[str]:
    """Apply pending migrations in filename order. Returns the ones applied."""
    applied = []

    # One transaction for everything. Postgres can roll back schema changes
    # (CREATE TABLE etc.), so a failing migration leaves the database exactly
    # as it was — never half-migrated.
    with conn.transaction():
        # If two deploys run this at once, the second waits here until the first
        # commits, then sees its work as already done. Released at commit.
        conn.execute("select pg_advisory_xact_lock(%s)", (MIGRATION_LOCK_ID,))

        conn.execute(
            """
            create table if not exists schema_migrations (
                name       text primary key,
                applied_at timestamptz not null default now()
            )
            """
        )
        # tuple_row: read plain tuples whatever row format the caller's connection uses.
        cur = conn.cursor(row_factory=tuple_row)
        done = {name for (name,) in cur.execute("select name from schema_migrations")}

        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.name in done:
                continue
            conn.execute(path.read_text())
            conn.execute("insert into schema_migrations (name) values (%s)", (path.name,))
            applied.append(path.name)

    return applied


def main() -> None:
    settings = Settings()
    with psycopg.connect(settings.database_url.get_secret_value()) as conn:
        applied = migrate(conn)
    print(f"applied: {', '.join(applied)}" if applied else "already up to date")


if __name__ == "__main__":
    main()
