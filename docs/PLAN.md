# Wishly — Implementation Plan

> **Purpose of this document.** This is the build plan for Wishly, structured so that
> coding agents (or humans) can pick up a single task at a time and execute it to a
> verifiable "done." Read [Conventions](#5-conventions-for-agents) before starting any task.
> Each task lists its dependencies, the files it touches, and acceptance criteria.

---

## 1. Product summary

Wishly lets a signed-in user track the birthdays, anniversaries, and custom occasions of
people they care about, and emails the user **reminders ahead of time** so they can prepare
(buy a gift, write a card, etc.).

- **Who logs in:** the *app user* (authenticated by Clerk).
- **Who receives the emails:** **the app user themselves**, by default. The reminder says
  "Mom's birthday is in 7 days." Clerk is the source of the user's email + name.
- **Extensibility (designed-in, not built yet):** `events.recipient_email` is nullable.
  `null` ⇒ send to the account owner (the default and only path we build now). A non-null
  value would let a future version send *to someone else* (e.g. a wish to the celebrant)
  without a schema redesign. **Do not build the non-null path in this phase.**

---

## 2. Locked technical decisions

| Area | Decision |
|---|---|
| Frontend | React + Vite + TypeScript SPA, deployed to **Cloudflare Pages** (`wishly.dev`) |
| Frontend auth | `@clerk/clerk-react` |
| API | **FastAPI** + uvicorn, containerized, exposed at `api.wishly.dev` via **Cloudflare Tunnel** |
| Orchestration | **Prefect** (self-hosted server + worker in the compose stack) |
| Database | **PostgreSQL 18.4** |
| ORM / migrations | **SQLAlchemy 2.0** (async for API, sync for the worker) + **Alembic** |
| Auth | **Clerk** — JWT verification on the API; webhook sync of users into Postgres |
| Email delivery | **Resend** (Python SDK) |
| Email templating | **Jinja2** + **premailer** (CSS inlining), pure Python. MJML optional at dev time only. |
| Python pkg mgmt | **uv** (never pip) |
| Python version | **3.12** (backend). Pin via `.python-version` and `requires-python = ">=3.12,<3.13"`. |
| Node version | **20 LTS+** (frontend build only) |
| Runtime split | **Python = all logic. JS = frontend only.** The SPA talks to the world only through the FastAPI API. |
| Deploy target | A single Linux host running Docker + Docker Compose (VPS or home server — interchangeable). |

---

## 3. Architecture

```
                 ┌─────────────────────────────────────────────┐
   Browser  ───► │ Cloudflare Pages  (wishly.dev)              │
                 │ React + Vite SPA + Clerk React SDK          │
                 └───────────────┬─────────────────────────────┘
                                 │ HTTPS + Clerk session JWT (Bearer)
                                 ▼
                 ┌─────────────────────────────────────────────┐
                 │ Cloudflare edge (api.wishly.dev)            │
                 │  CNAME ─► Cloudflare Tunnel                  │
                 └───────────────┬─────────────────────────────┘
                                 │ encrypted tunnel
   ┌──────────────────────── Docker host ────────────────────────────────┐
   │   cloudflared ──► api:8000  (FastAPI / uvicorn)                      │
   │                      │  verify Clerk JWT · CRUD · webhooks           │
   │                      ▼                                               │
   │                 postgres:5432 ◄──── prefect worker                   │
   │                      ▲                   │ hourly schedule           │
   │                      └───────────────────┘ render + send            │
   │                                           └──► Resend API ──► 📧     │
   └─────────────────────────────────────────────────────────────────────┘

   Clerk  ──webhook──► /webhooks/clerk    (user.* → upsert into users)
   Resend ──webhook──► /webhooks/resend   (bounce/complaint → suppress)
```

**Core principle:** FastAPI and Prefect are two entrypoints over **one shared Python package**
(same models, render code, Resend client). They never call each other; they meet at Postgres.

**Auth split:**
- *Request time* — the SPA sends the Clerk session JWT; FastAPI verifies it. Email/name come
  from a custom JWT claim (no extra round-trip).
- *Send time* — the worker has no JWT and cannot reach Clerk per send. It reads `users` from
  Postgres, which is kept current by Clerk **webhooks** (with provision-on-first-request as a
  fallback for a missed/raced webhook).

---

## 4. Repository layout (target)

```
wishly/
├── CLAUDE.md                 # conventions agents must follow (already created)
├── docs/
│   └── PLAN.md               # this file
├── .python-version           # 3.12
├── frontend/                 # React + Vite + TS SPA
│   ├── package.json
│   ├── vite.config.ts
│   ├── .env.example
│   └── src/
│       ├── main.tsx          # ClerkProvider + Router
│       ├── lib/api.ts        # fetch wrapper that attaches Clerk JWT
│       ├── routes/
│       └── components/
├── backend/
│   ├── pyproject.toml        # uv-managed; fastapi + prefect + shared deps
│   ├── alembic.ini
│   ├── alembic/
│   │   └── versions/
│   └── src/wishly/
│       ├── core/             # settings (pydantic-settings), logging
│       ├── db/               # engine/session factories, SQLAlchemy models
│       ├── email/            # Jinja2 templates, render service, Resend client
│       ├── api/              # FastAPI app
│       │   ├── main.py
│       │   ├── deps.py       # Clerk JWT auth dependency, db session dep
│       │   ├── schemas.py    # Pydantic request/response models
│       │   ├── routes/       # me.py, events.py, reminders.py, preferences.py
│       │   └── webhooks/     # clerk.py, resend.py
│       └── orchestration/    # Prefect: flows.py, tasks.py, due.py, session.py
└── infra/
    ├── docker-compose.yml    # full stack
    ├── docker-compose.dev.yml# postgres-only for local dev
    ├── Dockerfile.api
    ├── Dockerfile.worker
    ├── .env.example
    └── cloudflared/
        └── config.yml        # tunnel ingress
```

---

## 5. Conventions for agents

These are the **Definition of Done** rules. A task is not complete unless they hold.

1. **Python package management is `uv` only.** Add deps with `uv add <pkg>` (or `uv add --dev`).
   Never invoke `pip`. Run commands with `uv run <cmd>`.
2. **SQL files** are lowercase with underscores (e.g. `create_users.sql`). **SQL keywords are
   lowercase** (`select`, `from`, `where`). This applies to any raw SQL, seeds, and migration SQL.
3. **Lint/format/type-check must pass** before a task is done:
   - Backend: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src`.
   - Frontend: `npm run lint`, `npm run typecheck`, `npm run build`.
4. **Tests for the task's logic must pass:** `uv run pytest`. Pure logic (timezone math,
   idempotency, leap-year) requires unit tests in the same task that introduces it.
5. **No secrets in code or git.** All config via env vars; document new vars in the relevant
   `.env.example` and in [§11](#11-environment-variables).
6. **Keep the runtime split:** no business logic in the frontend; the SPA reaches the backend
   only via the FastAPI API.
7. **Migrations are the only way to change schema.** Never hand-edit a created table; add an
   Alembic revision. Every model change ships with its migration in the same task.
8. **Each task is self-contained and leaves `main` green.** If a task can't be finished without
   breaking the build, split it.

---

## 6. Data model

All tables, lowercase/underscore naming. `gen_random_uuid()` requires the `pgcrypto`
extension (enable in the first migration).

```sql
-- synced from Clerk; the source of truth for sending
create table users (
  id          text primary key,                       -- Clerk user id (user_...)
  email       text not null,
  first_name  text,
  last_name   text,
  timezone    text not null default 'UTC',            -- IANA tz, captured at onboarding
  send_hour   int  not null default 8,                -- 0-23, local hour to send
  deleted_at  timestamptz,                            -- soft delete on user.deleted
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

-- the occasions a user tracks
create table events (
  id              uuid primary key default gen_random_uuid(),
  user_id         text not null references users(id) on delete cascade,
  title           text not null,                      -- "Mom's birthday"
  event_type      text not null,                      -- birthday | anniversary | custom
  event_month     int  not null check (event_month between 1 and 12),
  event_day       int  not null check (event_day between 1 and 31),
  event_year      int,                                -- optional origin year → "Nth"
  message         text,                               -- user's custom note
  recipient_email text,                               -- null = send to account owner (DEFAULT)
  recipient_name  text,                               -- null = use owner's name
  template_id     uuid references templates(id),
  is_active       boolean not null default true,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);
create index events_user_id_idx on events (user_id);
create index events_month_day_idx on events (event_month, event_day) where is_active;

-- lead times per event (e.g. 30, 7, 1, 0 days before)
create table event_reminders (
  id          uuid primary key default gen_random_uuid(),
  event_id    uuid not null references events(id) on delete cascade,
  days_before int  not null check (days_before between 0 and 365),
  unique (event_id, days_before)
);

-- system + user-customized email templates
create table templates (
  id         uuid primary key default gen_random_uuid(),
  user_id    text references users(id) on delete cascade,  -- null = system template
  name       text not null,
  subject    text not null,                            -- Jinja2 source
  html       text not null,                            -- Jinja2 source (HTML)
  created_at timestamptz not null default now()
);

-- THE idempotency ledger — prevents double-sends
create table notification_log (
  id              uuid primary key default gen_random_uuid(),
  event_id        uuid not null references events(id) on delete cascade,
  days_before     int  not null,
  occurrence_date date not null,                       -- the specific dated occurrence
  status          text not null default 'pending',     -- pending | sent | failed | skipped
  resend_id       text,
  error           text,
  created_at      timestamptz not null default now(),
  sent_at         timestamptz,
  unique (event_id, days_before, occurrence_date)      -- ← the dedupe key
);

-- suppression list, fed by Resend bounce/complaint webhooks
create table suppressions (
  email      text primary key,
  reason     text not null,                            -- bounce | complaint | manual
  created_at timestamptz not null default now()
);
```

**Idempotency rule (memorize this):** the sender never sends without first winning an
`insert ... on conflict (event_id, days_before, occurrence_date) do nothing`. Winning the
insert grants the right to send. This makes double-sends structurally impossible.

---

## 7. The send algorithm (reference for Epic 5)

The flow runs **hourly**. For each run at `now_utc`:

1. For every non-deleted user, convert `now_utc` to the user's `timezone`. Keep only users
   whose **local hour == `send_hour`** (their send window for this run).
2. Compute the user's **local `today`**.
3. For each active event of those users, for each `event_reminders.days_before`:
   - `target = today + days_before`.
   - If `(target.month, target.day) == (event.event_month, event.event_day)` → a reminder is
     **due**, with `occurrence_date = target`. (Adding `days_before` to today, rather than
     subtracting from the occurrence, makes year-boundary reminders — e.g. a 30-day reminder
     in December for a January birthday — fall out for free.)
4. **Claim:** `insert into notification_log (event_id, days_before, occurrence_date, status)
   values (..., 'pending') on conflict do nothing returning id`. No row returned ⇒ already
   handled ⇒ skip.
5. **Send:** render the template, send via Resend, then `update notification_log set
   status='sent', resend_id=..., sent_at=now()` (or `status='failed', error=...`).
6. Skip any recipient address present in `suppressions`.

**Edge cases that must be handled (with tests):**
- **Feb 29 events** in non-leap years: observe on **Feb 28**. Encode in the `target` match.
- **Resend failure:** mark `failed`, let Prefect retry the task; the claim row already exists so
  retries don't duplicate — the retry updates the same row.
- **DST transitions:** rely on `zoneinfo`; never do manual offset math.

---

## 8. Epics & tasks

Task IDs are stable references for assigning work. **Depends-on** must be complete first.

### Epic 0 — Scaffold & tooling

**T0.1 — Backend package skeleton**
- *Depends on:* —
- *Scope:* Create `backend/` as a uv project. Set `requires-python = ">=3.12,<3.13"`, pin
  `.python-version` to `3.12`. Create `src/wishly/__init__.py` and the empty subpackages from
  §4 (`core`, `db`, `email`, `api`, `orchestration`). Add dev deps: `ruff`, `mypy`, `pytest`,
  `pytest-asyncio`. Configure ruff + mypy in `pyproject.toml`.
- *Files:* `backend/pyproject.toml`, `backend/.python-version`, `backend/src/wishly/**/__init__.py`.
- *Acceptance:* `uv sync` succeeds; `uv run ruff check .` and `uv run mypy src` pass on the empty tree.

**T0.2 — Local Postgres + env scaffolding**
- *Depends on:* —
- *Scope:* `infra/docker-compose.dev.yml` with a `postgres:18.4` service (named volume, healthcheck).
  Create `infra/.env.example` and `backend/.env.example` with the vars from §11. Add a `justfile`
  or `Makefile` with `db-up`, `db-down`, `api-dev`, `flow-run`, `worker`, `migrate`, `lint`, `test`.
- *Files:* `infra/docker-compose.dev.yml`, `infra/.env.example`, `backend/.env.example`, `justfile`.
- *Acceptance:* `just db-up` brings up Postgres; `psql` against `DATABASE_URL` connects.

**T0.3 — Settings & logging**
- *Depends on:* T0.1
- *Scope:* `core/settings.py` using `pydantic-settings` (`Settings` reads env: DB URL, Clerk keys,
  Resend keys, `EMAIL_FROM`, `APP_BASE_URL`, `ALLOWED_ORIGINS`, `ENVIRONMENT`). `core/logging.py`
  with structured logging setup.
- *Files:* `backend/src/wishly/core/settings.py`, `backend/src/wishly/core/logging.py`.
- *Acceptance:* `uv run python -c "from wishly.core.settings import settings; print(settings.environment)"`
  works with a populated `.env`; missing required vars raise a clear error.

**T0.4 — Frontend scaffold**
- *Depends on:* —
- *Scope:* `frontend/` via Vite React-TS template. Add `@clerk/clerk-react`, `react-router-dom`,
  `@tanstack/react-query`. ESLint + Prettier + a `typecheck` script. `.env.example` with
  `VITE_CLERK_PUBLISHABLE_KEY`, `VITE_API_BASE_URL`.
- *Files:* `frontend/**`.
- *Acceptance:* `npm run build`, `npm run lint`, `npm run typecheck` all pass.

### Epic 1 — Data layer

**T1.1 — SQLAlchemy models**
- *Depends on:* T0.1
- *Scope:* SQLAlchemy 2.0 declarative models for every table in §6 (`users`, `events`,
  `event_reminders`, `templates`, `notification_log`, `suppressions`) with relationships,
  constraints, and indexes.
- *Files:* `backend/src/wishly/db/models.py`, `backend/src/wishly/db/base.py`.
- *Acceptance:* models import cleanly; `mypy` passes; a metadata-create smoke test builds all tables
  against a throwaway SQLite/Postgres in a test.

**T1.2 — Engine & session factories**
- *Depends on:* T1.1, T0.3
- *Scope:* `db/session.py` exposing an **async** engine/sessionmaker (asyncpg) for the API and a
  **sync** engine/sessionmaker (psycopg) for the worker. A FastAPI `get_session` dependency.
- *Files:* `backend/src/wishly/db/session.py`.
- *Acceptance:* both engines connect to local Postgres; async + sync round-trip tests pass.

**T1.3 — Alembic + initial migration**
- *Depends on:* T1.1
- *Scope:* `alembic init`, wire `target_metadata` to the models, enable `pgcrypto` in the first
  revision, autogenerate the initial schema, verify upgrade/downgrade.
- *Files:* `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/versions/0001_*.py`.
- *Acceptance:* `just migrate` (alembic upgrade head) creates all §6 tables; `downgrade base` is clean.

**T1.4 — Seed system templates**
- *Depends on:* T1.3, T4.1
- *Scope:* A seed script inserting system templates (`user_id = null`) for birthday / anniversary /
  custom, referencing the HTML authored in T4.1.
- *Files:* `backend/src/wishly/db/seed.py`.
- *Acceptance:* `uv run python -m wishly.db.seed` is idempotent and inserts the system templates.

### Epic 2 — Auth & user sync

**T2.1 — Clerk JWT auth dependency**
- *Depends on:* T0.3, T1.2
- *Scope:* `api/deps.py` with a `CurrentUser` dependency: verify the Bearer token against Clerk
  (official `clerk-backend-api` SDK, or JWKS verification with PyJWT — check issuer + expiry),
  extract `sub`, `email`, `first_name`, `last_name` from the custom claim. Document the required
  Clerk **"Customize session token"** claim in code comments and §10.
- *Files:* `backend/src/wishly/api/deps.py`.
- *Acceptance:* a unit test with a signed test JWT passes; an expired/invalid token returns 401.

**T2.2 — App bootstrap + `/me` + provisioning**
- *Depends on:* T2.1
- *Scope:* `api/main.py` (FastAPI app, CORS from `ALLOWED_ORIGINS`, health route). `routes/me.py`:
  `GET /me` returns the user; **provision-on-first-request** — if `sub` not in `users`, insert from
  JWT claims. `PATCH /me` updates `timezone` + `send_hour`.
- *Files:* `backend/src/wishly/api/main.py`, `backend/src/wishly/api/routes/me.py`.
- *Acceptance:* first authenticated `GET /me` creates the user row and returns it; `PATCH /me`
  persists timezone/send_hour; integration test covers both.

**T2.3 — Clerk webhook → user sync**
- *Depends on:* T2.2
- *Scope:* `webhooks/clerk.py`: `POST /webhooks/clerk`, verify the **Svix** signature with the
  signing secret. Handle `user.created` / `user.updated` (upsert) and `user.deleted` (set
  `deleted_at`). Reject unsigned/invalid payloads with 400.
- *Files:* `backend/src/wishly/api/webhooks/clerk.py`.
- *Acceptance:* signed test payloads upsert/soft-delete correctly; bad signature → 400. Tested.

### Epic 3 — Events & reminders API

**T3.1 — Pydantic schemas**
- *Depends on:* T1.1
- *Scope:* request/response schemas for events, reminders, preferences in `api/schemas.py`.
  Validate `event_month`/`event_day` (incl. Feb 29 allowed, day-in-month sanity), `event_type`
  enum, `days_before` range, `send_hour` 0–23, IANA `timezone`.
- *Files:* `backend/src/wishly/api/schemas.py`.
- *Acceptance:* validation unit tests (valid + invalid cases) pass.

**T3.2 — Events CRUD**
- *Depends on:* T3.1, T2.2
- *Scope:* `routes/events.py` — `GET/POST/PATCH/DELETE /events`, scoped to `CurrentUser`. A user
  can only see/modify their own events.
- *Files:* `backend/src/wishly/api/routes/events.py`.
- *Acceptance:* CRUD integration tests pass; cross-user access returns 404/403.

**T3.3 — Reminders sub-resource**
- *Depends on:* T3.2
- *Scope:* manage `event_reminders` for an event: `PUT /events/{id}/reminders` (replace set) or
  add/remove endpoints. Enforce unique `days_before` per event.
- *Files:* `backend/src/wishly/api/routes/reminders.py`.
- *Acceptance:* setting/replacing reminders works; duplicates rejected; tested.

### Epic 4 — Email rendering & delivery

**T4.1 — Template structure + system HTML**
- *Depends on:* T0.1
- *Scope:* `email/templates/` with a base layout + birthday / anniversary / custom HTML using
  Jinja2 placeholders (`{{ recipient_name }}`, `{{ title }}`, `{{ days_before }}`,
  `{{ occurrence_date }}`, `{{ message }}`, `{{ manage_url }}`). Email-safe HTML + `<style>` block.
  *(Optional dev-time:* author in MJML, compile to these files; runtime stays pure Python.)*
- *Files:* `backend/src/wishly/email/templates/**`.
- *Acceptance:* templates render with sample context without Jinja errors.

**T4.2 — Render service**
- *Depends on:* T4.1
- *Scope:* `email/render.py` — given a template + context, render subject + HTML via Jinja2, then
  inline CSS with **premailer**. Include a plaintext fallback (strip tags).
- *Files:* `backend/src/wishly/email/render.py`.
- *Acceptance:* unit test asserts CSS is inlined and placeholders are filled; an `manage_url`
  (unsubscribe/preferences) is always present.

**T4.3 — Resend client**
- *Depends on:* T0.3, T4.2
- *Scope:* `email/resend_client.py` — thin wrapper over the `resend` SDK: `send_email(to, subject,
  html, text) -> resend_id`. Reads `RESEND_API_KEY`, `EMAIL_FROM`. Raises a typed error on failure.
- *Files:* `backend/src/wishly/email/resend_client.py`.
- *Acceptance:* unit test with the SDK mocked asserts correct payload + id extraction; a documented
  manual smoke test sends one real email in dev.

**T4.4 — Resend webhook + suppression**
- *Depends on:* T4.3, T2.2
- *Scope:* `webhooks/resend.py` — verify Resend signature; on `bounced`/`complained`, upsert
  `suppressions`. The sender (Epic 5) must consult `suppressions` before sending.
- *Files:* `backend/src/wishly/api/webhooks/resend.py`.
- *Acceptance:* signed events populate `suppressions`; bad signature → 400. Tested.

**T4.5 — Resend domain verification runbook**
- *Depends on:* —
- *Scope:* `docs/runbooks/resend-domain.md` — exact steps to verify `wishly.dev` in Resend and add
  SPF/DKIM/DMARC records in Cloudflare DNS, with the `EMAIL_FROM` convention (`reminders@wishly.dev`).
- *Files:* `docs/runbooks/resend-domain.md`.
- *Acceptance:* a reviewer can follow it end-to-end without external lookups.

### Epic 5 — Prefect send pipeline

**T5.1 — Prefect project + session helper**
- *Depends on:* T1.2, T4.3
- *Scope:* `orchestration/definitions.py`, `resources.py` — a DB resource (sync session) and a
  Resend client. Add `prefect` via uv; Prefect Cloud hosts the scheduler, so nothing is self-hosted.
- *Files:* `backend/src/wishly/orchestration/{definitions,resources}.py`.
- *Acceptance:* `uv run python -m wishly.orchestration.flows` runs the flow end to end with no errors.

**T5.2 — `find_due_notifications` op**
- *Depends on:* T5.1
- *Scope:* implement §7 steps 1–3 (timezone window via `zoneinfo`, `today + days_before` match,
  Feb 29 → Feb 28 rule). Returns a list of due `(event, days_before, occurrence_date)` tuples.
- *Files:* `backend/src/wishly/orchestration/ops.py`.
- *Acceptance:* **unit tests** cover timezone windowing, year-boundary reminders, leap-year, and
  send_hour gating — all green.

**T5.3 — Claim + send + record**
- *Depends on:* T5.2, T4.2
- *Scope:* for each due tuple: claim via `insert ... on conflict do nothing returning id`; skip if
  suppressed; render (T4.2) + send (T4.3); update `notification_log` to `sent`/`failed`. Resolve the
  recipient: `recipient_email or user.email`, `recipient_name or user.first_name`.
- *Files:* `backend/src/wishly/orchestration/ops.py`.
- *Acceptance:* idempotency test — running the job twice for the same date sends **once**. Failure
  path marks `failed` and is retryable without duplicating.

**T5.4 — Job, schedule, retries, alerting**
- *Depends on:* T5.3
- *Scope:* assemble ops into a job; an **hourly** `ScheduleDefinition`; op retry policy for transient
  Resend errors; a run-failure hook that logs/alerts.
- *Files:* `backend/src/wishly/orchestration/{schedules,definitions}.py`.
- *Acceptance:* the deployment and its hourly schedule appear in Prefect Cloud; a forced failure triggers the
  alert hook; retries don't duplicate sends.

### Epic 6 — Frontend

**T6.1 — Clerk provider, routing, protected routes**
- *Depends on:* T0.4
- *Scope:* `ClerkProvider` in `main.tsx`, sign-in/sign-up, a protected app shell, sign-out.
- *Files:* `frontend/src/main.tsx`, `frontend/src/routes/**`.
- *Acceptance:* unauthenticated users are redirected to sign-in; authenticated users reach the app.

**T6.2 — API client**
- *Depends on:* T6.1
- *Scope:* `lib/api.ts` — fetch wrapper that attaches the Clerk session token and targets
  `VITE_API_BASE_URL`; React Query hooks for `/me` and `/events`.
- *Files:* `frontend/src/lib/api.ts`, `frontend/src/lib/hooks.ts`.
- *Acceptance:* authenticated calls to `/me` succeed end-to-end against the local API.

**T6.3 — Onboarding (timezone + send hour)**
- *Depends on:* T6.2, T2.2
- *Scope:* first-run capture of `timezone` (default to `Intl.DateTimeFormat().resolvedOptions().timeZone`)
  and `send_hour`; `PATCH /me`.
- *Files:* `frontend/src/routes/onboarding.tsx`.
- *Acceptance:* timezone persists; subsequent loads skip onboarding.

**T6.4 — Events UI**
- *Depends on:* T6.2, T3.2, T3.3
- *Scope:* list / create / edit / delete events; manage reminder lead times; pick a template;
  optional custom message.
- *Files:* `frontend/src/routes/events/**`, `frontend/src/components/**`.
- *Acceptance:* full event lifecycle works against the API; form validation mirrors backend rules.

**T6.5 — Preferences / unsubscribe page**
- *Depends on:* T6.2
- *Scope:* a `manage_url` landing page (linked from every email) to pause reminders / manage prefs.
- *Files:* `frontend/src/routes/preferences.tsx`.
- *Acceptance:* the URL embedded in emails resolves to a working page.

### Epic 7 — Infra & deployment

**T7.1 — Dockerfiles**
- *Depends on:* T2.2, T5.4
- *Scope:* `Dockerfile.api` (uvicorn) and `Dockerfile.worker` (prefect worker), both uv-based,
  multi-stage, non-root.
- *Files:* `infra/Dockerfile.api`, `infra/Dockerfile.worker`.
- *Acceptance:* both images build; the API container serves `/health`.

**T7.2 — Full compose**
- *Depends on:* T7.1
- *Scope:* `infra/docker-compose.yml` with `postgres`, `api`, `prefect-worker`,
  `cloudflared`. Healthchecks, restart policies, named volume for Postgres, env via `.env`.
- *Files:* `infra/docker-compose.yml`.
- *Acceptance:* `docker compose up` brings the stack healthy; API reachable on the internal network.

**T7.3 — Cloudflare Tunnel**
- *Depends on:* T7.2
- *Scope:* `cloudflared/config.yml` ingress mapping `api.wishly.dev → http://api:8000`; runbook to
  create the tunnel, set `TUNNEL_TOKEN`, and add the DNS route.
- *Files:* `infra/cloudflared/config.yml`, `docs/runbooks/cloudflare-tunnel.md`.
- *Acceptance:* `api.wishly.dev/health` returns 200 from the public internet.

**T7.4 — Cloudflare Pages**
- *Depends on:* T6.4
- *Scope:* Pages build config (build command, output dir, env vars), SPA fallback routing, custom
  domain `wishly.dev`. Runbook included.
- *Files:* `docs/runbooks/cloudflare-pages.md`, frontend build config.
- *Acceptance:* `wishly.dev` serves the SPA; deep links resolve (SPA fallback works).

**T7.5 — Production webhooks**
- *Depends on:* T2.3, T4.4, T7.3
- *Scope:* register Clerk + Resend webhooks against `api.wishly.dev`; document the signing-secret
  env vars and verification.
- *Files:* `docs/runbooks/webhooks.md`.
- *Acceptance:* a real Clerk user event syncs to Postgres in prod; a Resend test event records a suppression.

### Epic 8 — Cross-cutting

**T8.1 — CI**
- *Depends on:* T0.1, T0.4
- *Scope:* GitHub Actions: backend (`ruff`, `mypy`, `pytest` against a Postgres service) and frontend
  (`lint`, `typecheck`, `build`). Run on PR.
- *Files:* `.github/workflows/ci.yml`.
- *Acceptance:* CI is green on a clean PR and red when a check fails.

**T8.2 — Observability**
- *Depends on:* T2.2, T5.4
- *Scope:* structured request logging + request IDs in the API; Prefect run logging; a `/health` and
  `/ready` (DB ping) endpoint. Optional: Cloudflare Workers observability notes for the edge.
- *Files:* API middleware, `docs/runbooks/observability.md`.
- *Acceptance:* logs are structured/queryable; `/ready` fails when Postgres is down.

**T8.3 — Backups & secrets**
- *Depends on:* T7.2
- *Scope:* a `pg_dump` backup cron (container or host), restore runbook, and a documented secrets
  strategy (`.env` + Docker secrets; never in images).
- *Files:* `infra/backup/*`, `docs/runbooks/backup-restore.md`.
- *Acceptance:* a documented backup → restore cycle succeeds on a scratch DB.

---

## 9. Sequencing & parallelization

**Critical path:** T0.1 → T1.1 → T1.2 → T2.1 → T2.2 → T3.2 → T4.2/T4.3 → T5.2 → T5.3 → T5.4 → T7.x.

**Parallelizable from the start (independent agents):**
- **Frontend track:** T0.4 → T6.1 → T6.2 (mock the API until T2.2 lands, then integrate).
- **Email track:** T4.1 → T4.2 (no DB dependency).
- **Infra track:** T0.2, T4.5, T7.3/T7.4 runbooks can be drafted early.

**Natural milestones:**
- **M1 — Auth spine:** T0.1–0.3, T1.1–1.3, T2.1–2.3. (User can sign in; users sync to Postgres.)
- **M2 — Events:** T3.1–3.3, T6.1–6.4. (User manages events in the UI.)
- **M3 — Sending:** T4.1–4.4, T5.1–5.4. (Reminders actually go out, idempotently.)
- **M4 — Production:** T7.1–7.5, T8.1–8.3. (Live at wishly.dev / api.wishly.dev.)

---

## 10. Clerk setup checklist (one-time, dashboard)

1. **Customize session token** with the claim:
   ```json
   { "email": "{{user.primary_email_address}}",
     "first_name": "{{user.first_name}}",
     "last_name": "{{user.last_name}}" }
   ```
2. Create a **webhook** → `https://api.wishly.dev/webhooks/clerk`, subscribe to
   `user.created`, `user.updated`, `user.deleted`. Copy the signing secret to
   `CLERK_WEBHOOK_SIGNING_SECRET`.
3. Note the **publishable key** (frontend) and **secret key** (API).

---

## 11. Environment variables

| Variable | Used by | Notes |
|---|---|---|
| `DATABASE_URL` | API, worker, Alembic | API uses asyncpg driver; worker/Alembic sync (psycopg) |
| `CLERK_SECRET_KEY` | API | Backend SDK / token verification |
| `CLERK_WEBHOOK_SIGNING_SECRET` | API | Svix verification for `/webhooks/clerk` |
| `CLERK_FRONTEND_API` | API | **Required.** Token issuer / JWKS origin; without it every request 401s |
| `RESEND_API_KEY` | API, worker | Email send |
| `RESEND_WEBHOOK_SIGNING_SECRET` | API | Verify `/webhooks/resend` |
| `EMAIL_FROM` | API, worker | e.g. `reminders@wishly.dev` (domain must be verified) |
| `APP_BASE_URL` | API, worker | `https://wishly.dev` — builds `manage_url` in emails |
| `ALLOWED_ORIGINS` | API | CORS allowlist, e.g. `https://wishly.dev,https://app.wishly.dev` |
| `ENVIRONMENT` | API, worker | `dev` / `prod` |
| `PREFECT_API_URL` | worker | `http://prefect-server:4200/api` (self-hosted) or a Cloud workspace URL |
| `PREFECT_API_KEY` | worker | Only needed when pointing at Prefect Cloud |
| `PREFECT_WORK_POOL` | worker | work pool the worker polls (e.g. `wishly-pool`) |
| `S3_BUCKET` | backup | destination bucket for hourly dumps |
| `S3_PREFIX` | backup | key prefix (default `wishly/postgres`) |
| `S3_ENDPOINT_URL` | backup | set for S3-compatible stores (R2/MinIO); empty for AWS |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | backup | bucket credentials |
| `AWS_DEFAULT_REGION` | backup | `us-east-1`; use `auto` for R2 |
| `TUNNEL_TOKEN` | cloudflared | Cloudflare Tunnel credential |
| `VITE_CLERK_PUBLISHABLE_KEY` | frontend | build-time |
| `VITE_API_BASE_URL` | frontend | `https://api.wishly.dev` |
| `VITE_APP_BASE_URL` | frontend | `https://app.wishly.dev` — dashboard origin; empty ⇒ same origin |

---

## 12. Out of scope (now) / future

- **Sending to the celebrant** (the non-null `recipient_email` path) — schema is ready; UI + flow not built.
- SMS / push channels, gift suggestions, shared/household calendars, recurring custom cadences
  (weekly/monthly), template WYSIWYG editor, paid tiers.
```
