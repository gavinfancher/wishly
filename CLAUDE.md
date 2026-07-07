# Wishly — agent instructions

Wishly emails signed-in users **reminders** ahead of birthdays/anniversaries they track, so
they can prepare. Full build plan: **`docs/PLAN.md`** (read the relevant task before starting).

## Architecture (one line)
React+Vite SPA (Cloudflare Pages) → FastAPI at `api.wishly.dev` (Cloudflare Tunnel) → Postgres;
**Dagster** runs the hourly send pipeline via **Resend**; **Clerk** is auth. FastAPI and Dagster
are two entrypoints over one shared Python package and meet only at Postgres.

## Stack (locked)
- Backend: Python **3.12**, FastAPI, SQLAlchemy 2.0 (async API / sync Dagster), Alembic, Dagster.
- Frontend: React + Vite + TypeScript, `@clerk/clerk-react`. **JS is frontend-only; all logic is Python.**
- Email: Resend + Jinja2 + premailer (pure Python; MJML optional at dev time).

## Hard rules (Definition of Done)
1. **Python pkg mgmt is `uv` only** — `uv add`, `uv run`. Never `pip`.
2. **SQL**: filenames lowercase_with_underscores; keywords lowercase (`select`, `from`, `where`).
3. **Schema changes only via Alembic migrations** — never hand-edit a created table. Model change
   ships with its migration in the same task.
4. **Idempotent sends**: never send without first winning
   `insert into notification_log ... on conflict (event_id, days_before, occurrence_date) do nothing`.
5. **No secrets in code/git** — env vars only; document new ones in `*.env.example` and PLAN §11.
6. **Timezones via `zoneinfo`** — never hand-roll offsets.
7. Each task leaves `main` green (lint + types + tests pass). If it can't, split it.

## Commands
- Backend lint/types/tests: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest`
- Migrate: `uv run alembic upgrade head`
- API dev: `uv run uvicorn wishly.api.main:app --reload`
- Dagster dev: `uv run dagster dev`
- Frontend: `npm run lint && npm run typecheck && npm run build`
- Local DB: `docker compose -f infra/docker-compose.dev.yml up -d`

## Conventions
- Backend code under `backend/src/wishly/`; tests beside or under `backend/tests/`.
- The user's reminder recipient defaults to their own Clerk email/name. `events.recipient_email`
  is nullable and **stays unused for now** (null ⇒ send to account owner).
