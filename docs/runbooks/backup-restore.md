# T8.3 — Backups, Restore & Secrets

How Wishly's Postgres is backed up, how to restore it, and how secrets are handled. The
backup/restore scripts live in `infra/backup/`. This procedure was verified end-to-end against a
scratch database: dump → upload to an S3-compatible store → download → restore into an empty
database → row-level verification.

**Dumps run hourly and are shipped off-host.** A dump sitting on the same machine as the database
is not a backup — that host dying takes both. The local volume is only a staging area; the copy
that matters is the one in the bucket.

---

## What is backed up

The entire `wishly` application database (the schema in `infra/sql/schema.sql`: `users`,
`events`, `event_reminders`, `templates`, `notification_log`, `suppressions`). Dumps use
Postgres **custom format** (`pg_dump -Fc`), which is compressed and supports selective/parallel
restore via `pg_restore`.

> Orchestration state (run history, schedules) lives in **Prefect Cloud**, not in this database,
> so there is nothing operational to back up here — the application database is the whole story.

---

## Scripts

| Script | Purpose |
|---|---|
| `infra/backup/backup.sh` | `pg_dump -Fc` to `$BACKUP_DIR`, upload to `s3://$S3_BUCKET/$S3_PREFIX/<day>/`, then prune local dumps older than `$RETENTION_DAYS`. |
| `infra/backup/restore.sh` | `pg_restore --clean --if-exists` a chosen dump into `$DATABASE_URL`. |

Both read `DATABASE_URL`. They run from the `infra/Dockerfile.backup` image, which is
`postgres:18.4` (so `pg_dump`/`pg_restore` match the cluster major version) plus the AWS CLI.

**Version matching is not optional.** A `pg_dump` newer than the server emits settings the older
server rejects — e.g. dumping with 18 and restoring into 16 fails on `SET transaction_timeout`.
Keep the image tag and the `postgres` service tag equal.

Environment:

| Var | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | — (required) | DSN of the database to dump/restore |
| `BACKUP_DIR` | `/backups` | Output directory for dumps |
| `RETENTION_DAYS` | `14` | Prune **local** dumps older than this many days |
| `S3_BUCKET` | — (required) | Destination bucket for the uploaded dump |
| `S3_PREFIX` | `wishly/postgres` | Key prefix inside the bucket; dumps are partitioned by day |
| `S3_ENDPOINT_URL` | unset | Set for S3-compatible stores (Cloudflare R2, MinIO); leave unset for AWS S3 |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | — | Bucket credentials |
| `AWS_DEFAULT_REGION` | `us-east-1` | Use `auto` for R2 |
| `BACKUP_S3_OPTIONAL` | `0` | `1` skips the upload instead of failing (local development only) |

### Remote retention

`RETENTION_DAYS` prunes only the local staging directory. Remote retention belongs to a bucket
lifecycle rule, so deleting old copies never depends on the backup host being alive:

- **AWS S3** — S3 → bucket → Management → Lifecycle rule → expire objects under the prefix after N days.
- **Cloudflare R2** — R2 → bucket → Settings → Object lifecycle rules → same idea.

At hourly cadence a 30-day window is ~720 dumps under `wishly/postgres/`, which is why the keys
are partitioned by day.

---

## Scheduled backups (container)

Overlay the backup sidecar on the running stack. It runs `backup.sh` on a daily loop into the
named volume `wishly_backups`:

```bash
docker compose -f infra/compose.yaml -f infra/compose.backup.yaml \
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
  wishly-backup:latest >> /var/log/wishly-backup.log 2>&1
```

---

## Manual backup

```bash
docker run --rm --network infra_app_net \
  -e DATABASE_URL="postgresql://wishly:${POSTGRES_PASSWORD}@postgres:5432/wishly" \
  -e BACKUP_DIR=/backups -v wishly_backups:/backups \
  -v "$PWD/infra/backup:/scripts:ro" \
  wishly-backup:latest
```

List existing dumps:

```bash
docker run --rm -v wishly_backups:/backups wishly-backup:latest ls -lh /backups
```

---

## Restore

Restore replaces objects in the **target** database (`--clean --if-exists`). The target must
exist; for a clean restore, create an empty database first.

1. Pick a dump:
   ```bash
   docker run --rm -v wishly_backups:/backups wishly-backup:latest ls -1 /backups
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
     --entrypoint /scripts/restore.sh wishly-backup:latest /backups/wishly_<timestamp>.dump
   ```
4. Verify (row counts / a known row), then, to make it live, either point the app at the restored
   DB or rename databases during a brief maintenance window.

### Restore from S3 (the real disaster path)

If the host is gone, the local volume is gone with it — pull the dump from the bucket instead.
List what is there, fetch one, and restore it:

```bash
# Newest key under the prefix
aws s3 ls s3://$S3_BUCKET/wishly/postgres/ --recursive | tail -5

# Fetch and restore (add --endpoint-url for R2/MinIO)
docker run --rm --network infra_app_net \
  -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_DEFAULT_REGION \
  -e DATABASE_URL="postgresql://wishly:wishly@postgres:5432/wishly" \
  --entrypoint sh wishly-backup:latest -c '
    aws s3 cp s3://'"$S3_BUCKET"'/wishly/postgres/<day>/<file>.dump /tmp/r.dump
    /scripts/restore.sh /tmp/r.dump'
```

`restore.sh` uses `pg_restore --clean --if-exists`, so the target database must already exist —
create it empty first for a fresh host.

### Disaster recovery (rebuild from empty volume)

1. `docker compose -f infra/compose.yaml --env-file infra/.env up -d postgres`
   (first boot creates `wishly` from `POSTGRES_DB`).
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
