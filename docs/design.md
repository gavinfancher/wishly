# Wishly API — v2

A user picks a date (repeats yearly) and how many days before it they want an
email, e.g. 7, 1 and 0. Wishly emails them a plain-text reminder at their chosen
hour, in their timezone. If code and this doc disagree, one of them is a bug.

## Endpoints

| Method | Path                     | Who         | Does                                 |
|--------|--------------------------|-------------|--------------------------------------|
| GET    | `/healthz`               | anyone      | Liveness — never touches the DB      |
| GET    | `/readyz`                | anyone      | Readiness — 503 if the DB is down    |
| POST   | `/v1/auth/signup`        | anyone      | Create account → session token (if sign-ups are on) |
| POST   | `/v1/auth/login`         | anyone      | Email + password → session token     |
| POST   | `/v1/auth/logout`        | session     | End this session                     |
| GET    | `/v1/me`                 | session     | Current user                         |
| PATCH  | `/v1/me`                 | session     | Timezone, send hour, finish onboarding |
| GET    | `/v1/reminders`          | session     | My reminders                         |
| POST   | `/v1/reminders`          | session     | Create                               |
| PUT    | `/v1/reminders/{id}`     | session     | Replace                              |
| DELETE | `/v1/reminders/{id}`     | session     | Delete                               |
| POST   | `/internal/run`          | run token   | Send everything due this hour        |

Another user's reminder ID returns 404, not 403.

## Auth

Email + password, handled by the API itself (`backend/src/wishly/auth.py`).

- **Passwords** are hashed with scrypt (Python's standard library), salted per
  user. At least 12 characters. Emails are compared lowercased.
- **Sessions** are random 256-bit tokens. The browser keeps the token and sends
  it as `Authorization: Bearer <token>`; the database keeps only its SHA-256,
  so a leaked `sessions` table can't be used to sign in. They last 30 days,
  and logout deletes the row so the token dies immediately.
- **Login** gives the same answer, after the same slow hash, for a wrong
  password and an unknown email, so it can't be used to discover accounts.
- **Sign-ups** can be closed with `WISHLY_SIGNUP_ENABLED=false`.

Opaque tokens checked against the database, rather than JWTs, because logout
and revocation are just a `delete`. The planned next step is moving this into
its own auth service, which the API would ask "whose token is this?".

## Data

```
users      id · email (unique) · password_hash · timezone · send_hour · onboarded_at · created_at
sessions   token_hash (PK) · user_id → users · created_at · expires_at
reminders  id · user_id → users · title · month · day · days_before int[] · created_at
sends      PK (reminder_id → reminders, days_before, occurrence_date) · sent_at
```

Ids are plain integers from Postgres (`generated always as identity`).
Sequential ids are safe here because every query is scoped to the caller's
`user_id`; guessing someone else's id gets a 404.

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
- Each hourly run also deletes expired sessions.
- **Known gaps:** no login rate limiting, no password reset, no email
  verification. Fine for a personal app with sign-ups closed.

## Running it

See the README for the full bring-up. In short:

- **Image:** `backend/Dockerfile`, published to GHCR by `.github/workflows/api.yml`.
- **Infra:** `infra/terraform` creates PlanetScale (database + two roles), the
  Cloudflare Tunnel and DNS, and the hourly trigger (EventBridge → Lambda). Its credentials
  are copied into Infisical by hand.
- **Host:** `infra/ansible` prepares the VM and registers a self-hosted GitHub
  Actions runner. Merging to `main` deploys: the runner runs `deploy.sh`, i.e.
  `infisical run -- docker compose up -d --wait` with `infra/compose.yaml`.
