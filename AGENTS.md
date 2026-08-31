# Wishly — agent instructions

Wishly emails signed-in users **reminders** ahead of birthdays/anniversaries they track, so
they can prepare. Full build plan: **`docs/PLAN.md`**; deployment and failover:
**`docs/DEPLOYMENT-PLAN.md`** (read the relevant task before starting).

## Architecture (one line)
React+Vite SPA (Cloudflare Pages) → FastAPI at `api.wishly.dev` (Cloudflare Tunnel) → Postgres
on **RDS**; **Prefect Cloud** schedules the hourly send, which executes in the local `worker`
container and delivers via **Resend**; **Clerk** is auth. FastAPI and the send pipeline are two
entrypoints over one shared Python package and meet only at Postgres.

## Stack (locked)
- Backend: Python **3.12**, FastAPI, SQLAlchemy 2.0 (async API / sync worker), Prefect.
- Frontend: React + Vite + TypeScript, `@clerk/clerk-react`. **JS is frontend-only; all logic is Python.**
- Email: Resend + Jinja2 + premailer (pure Python; MJML optional at dev time).

## Hard rules (Definition of Done)
1. **Python pkg mgmt is `uv` only** — `uv add`, `uv run`. Never `pip`.
2. **SQL**: filenames lowercase_with_underscores; keywords lowercase (`select`, `from`, `where`).
3. **Schema lives in `infra/sql/schema.sql`** — there are no migrations. A model change ships
   with the matching edit to that file in the same task. The test suite builds its database
   from it, so drift fails the tests. It uses `create table if not exists` and will **not**
   alter an existing table: a column change on a live database is hand-written SQL first.
4. **Idempotent sends**: never send without first winning
   `insert into notification_log ... on conflict (event_id, days_before, occurrence_date) do nothing`.
5. **No secrets in code/git** — env vars only; document new ones in `*.env.example` and
   DEPLOYMENT-PLAN §6.
6. **Timezones via `zoneinfo`** — never hand-roll offsets.
7. **All configuration is read in `core/settings.py`** — never `os.getenv` elsewhere. Note it
   reads `backend/.env` as well as the real environment, so tests must neutralise dev-only
   flags explicitly (see `tests/conftest.py`).
8. Each task leaves `main` green (lint + types + tests pass). If it can't, split it.

## Commands
Run backend commands from `backend/` (its own uv project).

- Lint + types: `uv run ruff check . && uv run ruff format --check . && uv run mypy src`
- Tests: `uv run pytest` — requires the **wishly_test** database. The fixtures
  truncate every table and refuse to start unless `DATABASE_URL` names a database
  ending in `_test`; pointing them at a real database once destroyed live data.
- Apply the schema: `psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f ../infra/sql/schema.sql`
- API dev (no containers): `uv run uvicorn wishly.api.main:app --reload`
- Run the send once: `uv run python -m wishly.orchestration.flows --once`
- Serve the deployments (what the worker container does): `uv run python -m wishly.orchestration.flows`
- Frontend: `npm run lint && npm run typecheck && npm run build` (from `frontend/`)
- Frontend dev server: `npm run dev` (from `frontend/`)
- Ship a backend change to the VM: `./infra/deploy.sh --host ubuntu@<vm>`.
  The frontend deploys itself on push to `main`; **the backend does not** — it is a
  container image built on the host, and the old one keeps passing health checks.

Full local stack (API, Postgres, worker, cloudflared tunnel):
```
docker compose -f infra/compose.yaml -f infra/compose.local.yaml --env-file infra/.env up -d
```
`compose.local.yaml` is an **overlay**, not a stack — both `-f` flags are required. It is also
the only place a Postgres container exists; production uses RDS.
`infra/.env` is rendered by the Infisical agent; see docs/runbooks/secrets.md.

## Conventions
- Backend code under `backend/src/wishly/`; tests beside or under `backend/tests/`.
- The user's reminder recipient defaults to their own Clerk email/name. `events.recipient_email`
  is nullable and **stays unused for now** (null ⇒ send to account owner).
