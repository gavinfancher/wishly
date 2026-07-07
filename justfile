# Wishly task runner. Run `just` (or `just --list`) to see available recipes.
# Backend recipes run inside ./backend (its own uv project).

set shell := ["bash", "-cu"]

backend := "backend"
compose := "infra/docker-compose.dev.yml"

# Show available recipes.
default:
    @just --list

# Start the local Postgres (detached) and wait for it to be healthy.
db-up:
    docker compose -f {{compose}} up -d

# Stop the local Postgres (keeps the named volume / data).
db-down:
    docker compose -f {{compose}} down

# Apply all Alembic migrations to head.
migrate:
    cd {{backend}} && uv run alembic upgrade head

# Lint, format-check, and type-check the backend.
lint:
    cd {{backend}} && uv run ruff check . && uv run ruff format --check . && uv run mypy src

# Run the backend test suite.
test:
    cd {{backend}} && uv run pytest

# Insert system email templates (idempotent).
seed:
    cd {{backend}} && uv run python -m wishly.db.seed

# Run the FastAPI app with autoreload (main.py arrives in a later task).
api-dev:
    cd {{backend}} && uv run uvicorn wishly.api.main:app --reload

# Run the Dagster dev UI + daemon (orchestration code arrives in a later task).
dagster-dev:
    cd {{backend}} && uv run dagster dev

# Run the Vite frontend dev server (needs frontend/.env — see frontend/.env.example).
web-dev:
    cd frontend && npm run dev
