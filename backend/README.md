# Wishly backend

Shared Python package powering the FastAPI API and the Dagster send pipeline over
one PostgreSQL database. See [`docs/PLAN.md`](../docs/PLAN.md) for the full build plan
and [`CLAUDE.md`](../CLAUDE.md) for conventions.

## Quick start

```bash
uv sync
uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest
```

Local Postgres + migrations:

```bash
docker compose -f ../infra/docker-compose.dev.yml up -d
uv run alembic upgrade head
```
