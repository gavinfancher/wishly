# Production deploy

End-to-end order of operations for a first deploy. Each step links to the runbook with the
detail; this page exists so the sequence and its dependencies are in one place.

Everything below assumes a single Linux host running Docker + Docker Compose, with the
database, API, and orchestration on that host, reachable only through a Cloudflare Tunnel.

---

## What runs where

| Piece | Where | Notes |
|---|---|---|
| SPA (marketing + dashboard) | Cloudflare Pages | one build, two hostnames |
| API | Docker host, `api:8000` | no published port; the tunnel reaches it |
| Postgres 18.4 | Docker host | no published port |
| Prefect server + worker | Docker host | self-hosted; see "Why not Prefect Cloud" below |
| Backups | Docker host → S3/R2 | hourly, off-host |
| Auth | Clerk | production instance |
| Email | Resend | verified sending domain |

---

## Pre-flight (accounts and secrets)

Nothing here needs the host. Collect these first — every later step blocks on them.

1. **Clerk production instance.** Note `sk_live_…`, `pk_live_…`, the **Frontend API host**
   (`CLERK_FRONTEND_API`, e.g. `https://clerk.wishly.dev`), and a webhook signing secret.
   Register **both** `wishly.dev` and `app.wishly.dev` on the instance.
   `CLERK_FRONTEND_API` is not optional — the API verifies tokens against that origin's JWKS,
   and without it every authenticated request returns 401 while the app otherwise looks fine.
2. **Resend.** Verify the sending domain and add SPF/DKIM/DMARC — see
   [resend-domain.md](resend-domain.md). Note `RESEND_API_KEY` and a webhook signing secret.
3. **Bucket for backups.** AWS S3 or Cloudflare R2. Create the bucket, an access key scoped to
   it, and a lifecycle rule expiring objects under `wishly/postgres/` — see
   [backup-restore.md](backup-restore.md).
4. **Cloudflare Tunnel token** for the host — see [cloudflare-tunnel.md](cloudflare-tunnel.md).

---

## 1. Host setup

```bash
git clone <repo> && cd wishly
cp infra/.env.example infra/.env
```

Fill in `infra/.env` with everything from pre-flight. It is git-ignored; keep it that way — it
is the only place production secrets exist on the host. Set `ENVIRONMENT=prod`, which also
permanently disables the API's `AUTH_DEV_BYPASS` regardless of what that flag says.

Confirm `ALLOWED_ORIGINS` lists **both** `https://wishly.dev` and `https://app.wishly.dev`, or
the dashboard's API calls fail CORS.

## 2. Bring up the stack

```bash
docker compose -f infra/docker-compose.yml --env-file infra/.env up -d --build
```

Order is enforced by health conditions, not luck: `postgres` becomes healthy → `migrate` runs
Alembic to head and exits → `api` and `prefect-worker` start → `cloudflared` waits for the API's
health check before serving. `prefect-deploy` creates the work pool and publishes the hourly
deployment once the Prefect server is healthy.

Verify:

```bash
docker compose -f infra/docker-compose.yml ps          # all services up/healthy
docker compose -f infra/docker-compose.yml logs api | tail
curl -s http://localhost:4200/api/health                # prefect server (host-local)
```

## 3. Tunnel

Follow [cloudflare-tunnel.md](cloudflare-tunnel.md) to route `api.wishly.dev` to `http://api:8000`.
Then, from off the host:

```bash
curl -i https://api.wishly.dev/health
```

## 4. Frontend

Follow [cloudflare-pages.md](cloudflare-pages.md). Set the build environment variables there —
including `VITE_APP_BASE_URL=https://app.wishly.dev` — and add both custom domains.

The production build **refuses to start** if `VITE_DEV_NO_AUTH` or `VITE_MOCK_API` is `true`, or
if the Clerk key is missing or still the placeholder. That guard exists because such a build
looks completely normal while bypassing auth entirely.

## 5. Webhooks

With `api.wishly.dev` live, register both (PLAN T7.5):

- Clerk → `https://api.wishly.dev/webhooks/clerk` (user sync)
- Resend → `https://api.wishly.dev/webhooks/resend` (bounces/complaints → suppression)

Put each signing secret in `infra/.env` and restart the API.

## 6. Backups

```bash
docker compose -f infra/docker-compose.yml -f infra/backup/docker-compose.backup.yml \
  --env-file infra/.env up -d --build backup
```

Then **verify a restore**, not just that files appear. A backup you have never restored is a
hypothesis. The procedure is in [backup-restore.md](backup-restore.md).

---

## Post-deploy checks

- [ ] `https://wishly.dev` loads; `https://app.wishly.dev` loads the dashboard
- [ ] Sign-up works and lands on onboarding; the user row appears in Postgres
- [ ] `https://api.wishly.dev/health` returns 200 from off-host
- [ ] Prefect UI shows the `hourly-send` deployment with an active schedule and a healthy worker
- [ ] One flow run completes (trigger manually rather than waiting for the hour)
- [ ] A test reminder email arrives and renders
- [ ] A dump has landed in the bucket, and a restore of it has been tried
- [ ] `docker compose logs` is free of stack traces

---

## Why not Prefect Cloud

Prefect Cloud's free plan offers **only managed work pools** — attempting to create a `process`,
`docker`, or `kubernetes` pool returns *"Your plan does not support hybrid or push work pools."*
Managed pools execute flows on Prefect's infrastructure, which cannot reach this Postgres: it
publishes no ports and lives behind the tunnel.

Letting Cloud run the flow would mean exposing the database to the internet, which trades the
entire private-by-default posture for a hosted scheduler. Self-hosting Prefect keeps the data
private, costs nothing, and runs the same flow code and the same `prefect.yaml`.

If you later move to a Prefect plan with hybrid pools, point `PREFECT_API_URL` at the workspace
and set `PREFECT_API_KEY`; drop the `prefect-server` service. Nothing else changes.
