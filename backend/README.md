# Wishly backend

The FastAPI API and the reminder send pipeline over one PostgreSQL database.
One process serves both: the send is a background task started by an hourly
EventBridge rule POSTing to `/internal/runs/send-reminders`.
See [`docs/PLAN.md`](../docs/PLAN.md) for the full build plan and
[`AGENTS.md`](../AGENTS.md) for conventions.

## Quick start

```bash
uv sync
uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest
```

Production Postgres is PlanetScale (see `infra/database-choice.md`). Locally:

```bash
docker compose -f ../infra/compose.local.yaml up -d
```

That brings up two databases. `wishly` is yours to develop against — apply the
schema to it once:

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f ../infra/sql/schema.sql
```

`wishly_test` is created empty alongside it and needs nothing: `pytest` applies
the schema itself and truncates every table between tests. **Never point the
suite at anything else.** It refuses any database whose name does not end in
`_test`, because pointing it at the development database once destroyed live
data — and a PlanetScale DSN is refused by that same guard.

There are no migrations — `infra/sql/schema.sql` is the schema, and it is
idempotent, so re-running it is safe.
