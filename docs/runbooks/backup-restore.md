# T8.3 — Backups, Restore & Secrets

How Wishly's Postgres is backed up, how to restore it, and how secrets are handled. The
backup/restore scripts live in `infra/backup/`. This procedure was verified end-to-end against a
scratch database (dump → restore into an empty DB → row-level verification).

---

## What is backed up

The entire `wishly` application database (the Alembic-managed schema from PLAN §6: `users`,
`events`, `event_reminders`, `templates`, `notification_log`, `suppressions`). Dumps use
Postgres **custom format** (`pg_dump -Fc`), which is compressed and supports selective/parallel
restore via `pg_restore`.

> Dagster's own state lives in the separate `wishly_dagster` database. It is **operational**, not
> business data (run history, schedules) — recreated automatically on a fresh deploy — so it is
> intentionally **not** part of this backup. Back it up too if you need to preserve run history:
> point `DATABASE_URL` at `.../wishly_dagster` and run the same script.

---

## Scripts

| Script | Purpose |
|---|---|
| `infra/backup/backup.sh` | `pg_dump -Fc` to `$BACKUP_DIR`, then prune dumps older than `$RETENTION_DAYS`. |
| `infra/backup/restore.sh` | `pg_restore --clean --if-exists` a chosen dump into `$DATABASE_URL`. |

Both read `DATABASE_URL` and are version-matched to the server when run from a `postgres:16`
image (so `pg_dump`/`pg_restore` match the cluster version).

Environment:

| Var | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | — (required) | DSN of the database to dump/restore |
| `BACKUP_DIR` | `/backups` | Output directory for dumps |
| `RETENTION_DAYS` | `14` | Prune dumps older than this many days |

---

## Scheduled backups (container)

Overlay the backup sidecar on the running stack. It runs `backup.sh` on a daily loop into the
named volume `wishly_backups`:

```bash
docker compose -f infra/docker-compose.yml -f infra/backup/docker-compose.backup.yml \
    --env-file infra/.env up -d backup
```

Tune cadence/retention via `BACKUP_INTERVAL_SECONDS` and `RETENTION_DAYS` in the overlay
(or `infra/.env`).

### Alternative: host cron

If you prefer cron on the Docker host over an always-on container, run the script inside a
throwaway postgres image on the shared network:

```cron
# 02:30 daily — dump the app DB to /var/backups/wishly on the host
30 2 * * * docker run --rm --network infra_app_net \
  -e DATABASE_URL="postgresql://wishly:${POSTGRES_PASSWORD}@postgres:5432/wishly" \
  -e BACKUP_DIR=/backups -v /var/backups/wishly:/backups \
  -v /path/to/wishly/infra/backup:/scripts:ro \
  postgres:16 sh /scripts/backup.sh >> /var/log/wishly-backup.log 2>&1
```

---

## Manual backup

```bash
docker run --rm --network infra_app_net \
  -e DATABASE_URL="postgresql://wishly:${POSTGRES_PASSWORD}@postgres:5432/wishly" \
  -e BACKUP_DIR=/backups -v wishly_backups:/backups \
  -v "$PWD/infra/backup:/scripts:ro" \
  postgres:16 sh /scripts/backup.sh
```

List existing dumps:

```bash
docker run --rm -v wishly_backups:/backups postgres:16 ls -lh /backups
```

---

## Restore

Restore replaces objects in the **target** database (`--clean --if-exists`). The target must
exist; for a clean restore, create an empty database first.

1. Pick a dump:
   ```bash
   docker run --rm -v wishly_backups:/backups postgres:16 ls -1 /backups
   ```
2. (Fresh DB) create an empty target — `DROP/CREATE DATABASE` cannot run in a transaction, so use
   separate statements:
   ```bash
   docker exec wishly-postgres psql -U wishly -d postgres -c "create database wishly_restore;"
   ```
3. Restore:
   ```bash
   docker run --rm --network infra_app_net \
     -e DATABASE_URL="postgresql://wishly:${POSTGRES_PASSWORD}@postgres:5432/wishly_restore" \
     -v wishly_backups:/backups -v "$PWD/infra/backup:/scripts:ro" \
     postgres:16 sh /scripts/restore.sh /backups/wishly_<timestamp>.dump
   ```
4. Verify (row counts / a known row), then, to make it live, either point the app at the restored
   DB or rename databases during a brief maintenance window.

### Disaster recovery (rebuild from empty volume)

1. `docker compose -f infra/docker-compose.yml --env-file infra/.env up -d postgres`
   (first boot recreates `wishly` and `wishly_dagster` via the init script).
2. Restore the latest dump into `wishly` (steps above; the empty DB already exists).
3. Bring up the rest of the stack — `migrate` is a no-op since the schema is already present.

---

## Secrets strategy

- **Never in images or git.** `.dockerignore` excludes every `.env`/`.env.*` (except
  `*.env.example`); images receive config only at runtime via `env_file`/`environment`.
- **Source of truth is `infra/.env`** on the host, created from `infra/.env.example`, readable
  only by the deploy user (`chmod 600`). It is git-ignored.
- **Documented variables only.** Every secret is listed in PLAN §11 and the relevant
  `*.env.example`. Adding a new one means updating both.
- **Rotation.** Clerk/Resend keys rotate in their dashboards; the tunnel token rotates per the
  Cloudflare Tunnel runbook. After rotating, update `infra/.env` and
  `docker compose ... up -d <service>` to restart with the new value.
- **Hardening path (optional).** For multi-host or stricter setups, switch `env_file` to Docker
  secrets (`/run/secrets/*`) — the app reads the same variable names, so only the delivery
  mechanism changes.
- **Backups contain data, not app secrets**, but treat dump files as sensitive (user emails/names)
  — keep `wishly_backups` access-restricted and encrypt off-host copies.
