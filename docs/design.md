# Wishly API — v2 design

Status: draft (Step 0). This is the contract we build against. If code and this
doc disagree, one of them is a bug.

## Goals

- Small enough to explain every line.
- Correct before clever: no double-sends, no cross-user data leaks.
- Operable: health checks a load balancer / watchdog can trust, logs you can
  grep by request ID, failures that say what went wrong.

## Non-goals (for now)

- Custom HTML templates per user.
- Sending to anyone other than the account owner (`recipient_email`).
- Pagination beyond "most recent N" — two users don't need cursors yet.

## Resources

| Resource       | What it is                                                          |
|----------------|---------------------------------------------------------------------|
| `User`         | The account. Identity lives in Clerk; we store prefs (tz, send hour). |
| `Event`        | A yearly date to be reminded of (birthday, anniversary, custom).    |
| `Reminder`     | "N days before" an event. An event has a *set* of these.            |
| `Notification` | One row per email we attempted. Read-only to users. Also our dedupe ledger. |

## Endpoints

Base path `/v1`. The frontend's `VITE_API_BASE_URL` includes `/v1`, so its
existing paths (`/me`, `/events`, …) keep working unchanged.

### Public (Clerk JWT required)

| Method | Path                      | Purpose                              | Success |
|--------|---------------------------|--------------------------------------|---------|
| GET    | `/me`                     | Current user (created on first call) | 200     |
| PATCH  | `/me`                     | Update timezone / send hour / onboarded | 200  |
| DELETE | `/me`                     | Delete account and all data          | 204     |
| POST   | `/me/test-email`          | Send a test reminder to yourself     | 202     |
| GET    | `/events`                 | List my events (with reminders)      | 200     |
| POST   | `/events`                 | Create event (optionally with reminders) | 201 |
| GET    | `/events/{id}`            | One event                            | 200     |
| PATCH  | `/events/{id}`            | Partial update                       | 200     |
| DELETE | `/events/{id}`            | Delete                               | 204     |
| PUT    | `/events/{id}/reminders`  | Replace the whole reminder set       | 200     |
| GET    | `/notifications`          | My 100 most recent sends             | 200     |

Another user's event returns **404, not 403** — we don't confirm it exists.

### Internal (shared secret)

| Method | Path              | Caller      | Purpose                         |
|--------|-------------------|-------------|---------------------------------|
| POST   | `/internal/runs`  | EventBridge | Send every reminder due this hour |

### Webhooks (Svix signature)

| Method | Path               | Caller | Purpose                                  |
|--------|--------------------|--------|------------------------------------------|
| POST   | `/webhooks/resend` | Resend | Bounces/complaints → suppression list    |
| POST   | `/webhooks/clerk`  | Clerk  | User deleted/updated outside our app     |

### Ops (no auth, outside `/v1`)

| Path       | Meaning                                         | Touches DB? |
|------------|-------------------------------------------------|-------------|
| `/healthz` | Liveness: the process is up and serving.        | No          |
| `/readyz`  | Readiness: we can do real work (DB reachable).  | Yes         |

## Auth model

Three callers, three mechanisms:

1. **Browser** → Clerk session JWT, verified locally against Clerk's JWKS
   (no network call per request once keys are cached).
2. **EventBridge** → static bearer token from Secrets Manager, compared in
   constant time.
3. **Resend / Clerk** → Svix HMAC signature over the raw body + timestamp (rejects
   replays older than 5 minutes).

Users are provisioned **just-in-time**: the first authenticated request upserts
a `users` row from the JWT's `sub` and `email` claims.

## Errors

Every error is RFC 9457 Problem Details (`application/problem+json`):

```json
{
  "type": "about:blank",
  "title": "Not Found",
  "status": 404,
  "detail": "Event not found",
  "request_id": "01J9…"
}
```

`request_id` is also returned as the `X-Request-ID` header and appears on
every log line for that request.

## Data model

```
users            id (Clerk sub, PK) · email · timezone · send_hour (0–23)
                 onboarded_at · created_at · updated_at

events           id (uuid PK) · user_id → users (cascade) · title
                 event_type (birthday|anniversary|custom)
                 event_month · event_day · event_year? · message?
                 is_active · created_at · updated_at

event_reminders  event_id → events (cascade) · days_before (0–365)
                 PK (event_id, days_before)

notification_log id · user_id → users (cascade) · event_id? → events (set null)
                 days_before · occurrence_date · is_test · status
                 (pending|sent|failed|skipped) · provider_id · error
                 created_at · sent_at
                 UNIQUE (event_id, days_before, occurrence_date)

suppressions     email (PK) · reason · created_at
```

Schema changes go through migrations (Alembic) — no hand-applied SQL.

## The hourly run (sketch — detailed in Step 5)

Every reminder has a **send moment**: `(occurrence_date - days_before)` at
`send_hour`, in the user's timezone. A reminder is **due** when its send
moment falls in **the current hour or the previous one** (compared in whole
hours, so a run at 9:00:05 still catches an 8:00 moment). Older than that, the
reminder is worthless and is never sent.

Each run:

1. EventBridge calls `POST /internal/runs` at the top of every hour.
2. Select every due reminder.
3. **Claim** each one: `INSERT … ON CONFLICT DO NOTHING RETURNING id` into
   `notification_log`. The database lets exactly one insert win; every other
   concurrent run gets zero rows back and skips it.
4. The winner sends via Resend with `Idempotency-Key: <notification_log.id>`.
5. Mark the row `sent` / `failed` / `skipped` (suppressed address).

Rows left `pending` or `failed` (crash or Resend error mid-send) are retried by
the next run while still inside the window, **reusing the same idempotency
key** — so if the first attempt actually reached Resend, Resend returns the
original result instead of sending a second email.

Why not "check the log, then send"? Two concurrent runs can both check, both
see nothing, and both send (a check-then-act race). The unique constraint moves
the decision into a single atomic database operation.

## Packaging

One image, built from one `Dockerfile`, pushed to GHCR. It contains the API,
the run endpoint, webhooks, and migrations (`alembic upgrade head`, run as a
one-off command with the same image before the new version starts). There is
no scheduler or worker process. `cloudflared` runs beside it as Cloudflare's
stock image — not built by us.

## Decisions

- **Feb 29 events** fall on **Feb 28** in non-leap years. Day-of-month is also
  validated against the month on write (no Apr 31; Feb 29 allowed).
- **Missed runs send at most 1 hour late.** Past that the reminder is dropped
  (and logged as a warning). An outage longer than an hour loses reminders —
  acceptable for a reminder app; that's what the ECS failover is for.
- **No drift with Clerk.** Clerk is the source of truth for identity:
  - `DELETE /me` deletes the user **in Clerk** via the Clerk Backend API, then
    deletes our rows.
  - A Clerk webhook (`user.deleted`, `user.updated`) covers changes made
    outside our app (dashboard deletes, email changes). Handlers are
    idempotent, so our own `DELETE /me` echoing back as a webhook is a no-op.
