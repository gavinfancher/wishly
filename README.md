# Wishly

Wishly emails you ahead of the birthdays and anniversaries you track, so you have
time to actually do something about them. Add an occasion, choose how many days'
warning you want, and the reminder arrives at an hour you pick, in your timezone.

It is a personal project, built to be run properly rather than just demoed: real
auth, real email delivery, an idempotent send pipeline, and a documented failover
onto AWS when the home server goes dark.

---

## How it works

```
   Browser
      │  HTTPS
      ▼
   Cloudflare Pages ──── the SPA (React + Vite)
      │
      │  Bearer <Clerk session token>
      ▼
   Cloudflare Tunnel ──► FastAPI ──┐
                                   ├──► Postgres (RDS)
   Prefect Cloud ──► worker ───────┘         │
   (schedule only)   (hourly send)           │
                          └──► Resend ───► inbox
```

FastAPI and the send pipeline are two entrypoints over **one shared Python
package**. They never call each other; they meet at Postgres. That is the whole
architecture, and it is why the worker can run on a different machine from the API
without anything being rewired.

| Layer | Choice |
|---|---|
| Frontend | React + Vite + TypeScript, Clerk for auth |
| API | FastAPI, SQLAlchemy 2.0 (async), Python 3.12 |
| Send pipeline | Prefect (Cloud control plane, local execution) |
| Email | Resend + Jinja2 + premailer |
| Database | Postgres 18 |
| Hosting | Cloudflare Pages + Tunnel, Proxmox VM, AWS standby |

**JavaScript is frontend-only.** Every piece of logic — due-date math, timezone
handling, rendering, sending — is Python, so there is exactly one place a rule can
live.

---

## The two things worth reading

If you only look at two files, make it these.

**`backend/src/wishly/orchestration/due.py`** — the due-date logic, kept free of
Prefect and the database so the riskiest part of the app is unit-testable in
isolation. The matching is *additive*: for a lead time of N days, it asks whether
`today + N` lands on the event's month and day, rather than subtracting N from the
next occurrence. Year-boundary reminders then fall out for free — a 30-day
reminder evaluated in December naturally targets a January birthday — and the
Feb 29 → Feb 28 rule is three lines instead of a special case everywhere.

**`backend/src/wishly/orchestration/tasks.py`** — the send, which never sends
without first winning:

```sql
insert into notification_log (event_id, days_before, occurrence_date, status)
values (...)
on conflict (event_id, days_before, occurrence_date) do nothing
returning id
```

Winning the insert *is* the permission to send. Losing it means someone already
handled this occurrence. Double sends are impossible by schema rather than by
care, so retries are free: a retry updates the row it already claimed.

---

## Running it locally

Requires [uv](https://docs.astral.sh/uv/), Node 20+, and Docker.

```bash
# 1. Database
docker compose -f infra/compose.yaml -f infra/compose.local.yaml \
  --env-file infra/.env up -d postgres

# 2. Schema
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f infra/sql/schema.sql

# 3. API
cd backend && cp .env.example .env   # then fill it in
uv run uvicorn wishly.api.main:app --reload

# 4. Frontend
cd frontend && cp .env.example .env
npm install && npm run dev
```

The UI runs without any backend at all with `VITE_MOCK_API=true`, and against a
real backend without Clerk with `AUTH_DEV_BYPASS=true` (non-production only —
`ENVIRONMENT=prod` disables it permanently, whatever the flag says).

The full stack, including the tunnel:

```bash
docker compose -f infra/compose.yaml -f infra/compose.local.yaml \
  --env-file infra/.env up -d
```

Both `-f` flags are required — `compose.local.yaml` is an overlay, not a stack.

### Checks

```bash
cd backend
uv run ruff check . && uv run ruff format --check . && uv run mypy src
uv run pytest                       # needs the wishly_test database

cd ../frontend
npm run lint && npm run typecheck && npm run build
```

The tests build their schema from `infra/sql/schema.sql` — the same file that
provisions production — so a model that has drifted from it fails the suite rather
than production. They also refuse to run against any database whose name does not
end in `_test`, because the fixtures truncate every table.

---

## Notes on a few decisions

**No migrations.** `infra/sql/schema.sql` is the schema, applied with
`create table if not exists`. For a single-user app whose schema changes a few
times a year, a migration tool is more machinery than the problem deserves. The
cost is real and worth naming: this will not *alter* an existing table, so a
column change on a live database is hand-written SQL. The [deployment
plan](docs/DEPLOYMENT-PLAN.md) says so where it matters.

**Prefect for one hourly job.** Overkill on the face of it, and cron is one flag
away (`--once`). It stays because the send window is exactly one hour wide, so a
tick missed during a reboot is a reminder that is simply never sent. Prefect keeps
that run pending instead of dropping it. The schedule lives in Prefect Cloud
rather than on the server, so it survives the server it schedules.

**The database left the house first.** Moving Postgres to RDS is what makes the
AWS standby simple: both application hosts are stateless and point at the same
database, so a failover moves compute and nothing else. Nothing is promoted,
replicated, or reconciled.

---

## Layout

```
backend/     FastAPI app, send pipeline, models — one package, two entrypoints
  src/wishly/
    api/            routes, auth, webhooks
    core/           settings (the only place the environment is read)
    db/             models, session factories, seed
    email/          Jinja2 rendering + Resend client
    orchestration/  due-date logic, Prefect flows and tasks
frontend/    React + Vite SPA
infra/       compose files, Dockerfiles, schema.sql, backup, failover watchdog
docs/        PLAN.md (product), DEPLOYMENT-PLAN.md (ops), runbooks/
```

---

## Documentation

- [docs/PLAN.md](docs/PLAN.md) — the product and the build plan
- [docs/DEPLOYMENT-PLAN.md](docs/DEPLOYMENT-PLAN.md) — topology, failover, open tasks
- [docs/runbooks/](docs/runbooks/) — local dev, deploys, secrets, backup/restore,
  Cloudflare, Resend, the AWS VPC and Tailscale setup

---

## License

[MIT](LICENSE).
