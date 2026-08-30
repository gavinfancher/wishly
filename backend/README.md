# Wishly backend

Shared Python package powering the FastAPI API and the Prefect send pipeline over
one PostgreSQL database. Two entrypoints, one package; they meet only at Postgres.
See [`docs/PLAN.md`](../docs/PLAN.md) for the full build plan and
[`AGENTS.md`](../AGENTS.md) for conventions.

## Quick start

```bash
uv sync
uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest
```

Local Postgres + schema:

```bash
docker compose -f ../infra/compose.yaml -f ../infra/compose.local.yaml \
  --env-file ../infra/.env up -d postgres
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f ../infra/sql/schema.sql
```

There are no migrations — `infra/sql/schema.sql` is the schema, and it is
idempotent, so re-running it is safe.
