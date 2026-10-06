# Wishly API — v2

A user picks a date (repeats yearly) and how many days before it they want an
email, e.g. 7, 1 and 0. Wishly emails them a plain-text reminder at their chosen
hour, in their timezone. If code and this doc disagree, one of them is a bug.

## Endpoints

| Method | Path                     | Who         | Does                                 |
|--------|--------------------------|-------------|--------------------------------------|
| GET    | `/healthz`               | anyone      | Liveness — never touches the DB      |
| GET    | `/readyz`                | anyone      | Readiness — 503 if the DB is down    |
| GET    | `/v1/me`                 | Clerk JWT   | Current user (created on first call) |
| PATCH  | `/v1/me`                 | Clerk JWT   | Timezone, send hour, finish onboarding |
| GET    | `/v1/reminders`          | Clerk JWT   | My reminders                         |
| POST   | `/v1/reminders`          | Clerk JWT   | Create                               |
| PUT    | `/v1/reminders/{id}`     | Clerk JWT   | Replace                              |
| DELETE | `/v1/reminders/{id}`     | Clerk JWT   | Delete                               |
| POST   | `/internal/run`          | run token   | Send everything due this hour        |

Another user's reminder ID returns 404, not 403.

## Data

```
users      id (Clerk sub) · email · timezone · send_hour · onboarded_at · created_at
reminders  id · user_id → users · title · month · day · days_before int[] · created_at
sends      PK (reminder_id → reminders, days_before, occurrence_date) · sent_at
```

Plain SQL through psycopg. The whole schema is `infra/sql/schema.sql`: one
file you read, then apply with `psql` as the `wishly_schema` role. It's
idempotent (`if not exists`) and runs in a transaction. The API connects as
`wishly_app`, which can read and write rows but can't create or drop tables.

## The hourly run

EventBridge invokes a small Lambda at the top of every hour, which calls
`POST /internal/run`, logs the result, and notifies by ntfy. A reminder is
**due** when its send moment — `send_hour` local time, `days_before` days before
the date — falls in this hour or the previous one. So a missed run sends up to
one hour late; after that the reminder is dropped.

For each due reminder:

1. **Claim:** `insert into sends … on conflict do nothing`. The primary key lets
   exactly one insert win, so overlapping or retried runs can't double-send.
2. **Send** via Resend, with `Idempotency-Key: <reminder>/<days>/<date>`.
3. **On failure, release** the claim (delete the row), so the next run retries.

## Decisions

- Feb 29 dates fall on Feb 28 in non-leap years.
- No v1 data migration; v1 tables are dropped before the first deploy.
- Users are created just-in-time from the Clerk token (`sub`, `email` claims).
- **Known gap:** a user deleted in the Clerk dashboard keeps their rows (and
  emails) until removed by hand. Fix later with a Clerk `user.deleted` webhook.

## Running it

See the README for the full bring-up. In short:

- **Image:** `backend/Dockerfile`, published to GHCR by `.github/workflows/api.yml`.
- **Infra:** `infra/terraform` creates PlanetScale (database + two roles), the
  Cloudflare Tunnel and DNS, and the hourly trigger (EventBridge → Lambda). Its credentials
  are copied into Infisical by hand.
- **Host:** `infra/ansible` prepares the VM and registers a self-hosted GitHub
  Actions runner. Merging to `main` deploys: the runner runs `deploy.sh`, i.e.
  `infisical run -- docker compose up -d --wait` with `infra/compose.yaml`.
