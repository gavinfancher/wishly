# Wishly — Deployment Plan

Companion to [PLAN.md](PLAN.md), which covers building the product. This file covers
**getting it deployed and keeping the data safe.** It expands PLAN.md Epic 7 and replaces
§2's "single Linux host" deploy target with a two-VM split.

Origin: `ideas.md` at the repo root, scoped down 2026-08-20. See §7 for what was
deliberately cut.

---

## 1. Target

```
   Browser
      │  HTTPS
      ▼
   Cloudflare edge
      ├── Pages ──────── wishly.dev, app.wishly.dev   (static SPA, already live)
      │
      └── api.wishly.dev
             │  Cloudflare Tunnel
             ▼
   ┌─── Proxmox VE (home) ──────────────────────────────────────┐
   │                                                             │
   │  vm-wishly  (stateless)          vm-db  (the data tier)     │
   │  ┌──────────────────────┐        ┌───────────────────────┐  │
   │  │ cloudflared          │        │ postgres 18.4 :5432   │  │
   │  │ api:8000             │───────►│   ├── wishly          │  │
   │  │ prefect-server + UI  │  VPN   │   └── prefect         │  │
   │  │ prefect-worker       │───────►│                       │  │
   │  └──────────────────────┘        │ backup → S3, last 48  │  │
   │                                  └───────────────────────┘  │
   └─────────────────────────────────────────────────────────────┘

   Infisical Cloud ──agent──► renders infra/.env on each VM
   Clerk (auth) · Resend (email) · S3 (backups)
```

Two VMs, both already provisioned (4 vCPU / 7.8 GB / 48 GB, Ubuntu 24.04, Docker 29.7.2,
Tailscale):

| Role | Host |
|---|---|
| `vm-db` | `postgres.vm.homecloud.gavinf.com` (`100.99.169.16`) |
| `vm-wishly` | `wishly-vm.vm.homecloud.gavinf.com` (`100.79.129.122`) |

`vm-db` is a **general Postgres host** and predates Wishly: the server runs as
`homecloud-postgres` from `/home/ubuntu/docker-compose.yml` and is shared infrastructure.
**Wishly does not manage it** — it is a *tenant*, with its own `wishly` and `prefect`
databases and login roles created by `infra/vm-db/sql/create_tenant.sql`. That is exactly
the relationship the eventual managed database will impose, which is the point.

`vm-wishly` runs everything else.

The VPN is the trust boundary; no TLS on the database connection yet (§7).

**VM specs, Proxmox settings, and the full stand-up procedure live in
[runbooks/production-deploy.md](runbooks/production-deploy.md).** Short version: both VMs
2 vCPU / 4 GB, 40 GB for `vm-wishly` and 60 GB for `vm-db`.

### 1.1 vm-wishly holds no state

With Prefect's server state moved to `vm-db` (T2), nothing on `vm-wishly` needs to survive
a rebuild — no volumes worth backing up, no data to migrate. It can be destroyed and
recreated from the compose file and Infisical at any time. That is the same split the
future managed-database setup will have, which is the point of simulating it now.

---

## 2. How Prefect fits

Worth stating explicitly, because the three services aren't self-explanatory and the
mental model people usually bring is wrong.

**Prefect is pull-based. The server never reaches out to anything.**

| Service | Lifetime | Role |
|---|---|---|
| `prefect-server` | always on | Scheduler, API, UI, run state. Holds the deployment and its cron; creates run records at the top of each hour. **Never executes flow code.** |
| `prefect-deploy` | one-shot at boot | Runs `prefect deploy --all`, which reads `backend/prefect.yaml` and upserts the deployment + schedule onto the server. Idempotent, then exits. |
| `prefect-worker` | always on | Long-polls the server for runs in `wishly-pool` and **executes the flow in its own container**. This is where your code runs, so it holds `DATABASE_URL` and `RESEND_API_KEY`. |

Because the pool is `--type process`, the worker runs the flow as a subprocess inside
itself rather than spawning a container per run. Combined with `pull: null` in
`prefect.yaml`, that means **the flow code ships inside the worker image** — change
anything under `orchestration/` and the worker must be rebuilt and restarted. A
`prefect deploy` alone will not pick it up.

**If you later want Prefect to run work on another VM**, the server does not push to it —
you run another worker there, polling a different pool. Workers are the unit of execution
placement; pools are the routing. Splitting the server onto its own VM is not what enables
that, and would add a failure domain to the critical path (see below) for no gain today.

### 2.1 Why the server is worth its keep

For a single hourly cron, plain `cron` calling `python -m wishly.orchestration.flows` would
work — `flows.py:53` supports it directly. The server earns its place for one specific reason:

`due.py:44` gates sends on `local_now(...).hour == send_hour`, evaluated against
`datetime.now()` at execution time (`tasks.py:136`). So the send window is the whole hour,
and **a missed tick is a permanently lost reminder** — the next hour's run no longer matches
that user's `send_hour`, and there is no catch-up pass.

Prefect closes that gap. A run scheduled at 14:00 that nothing claims sits in `Late` rather
than evaporating, so a worker that comes back at 14:20 still executes it, the local hour is
still 14, and the reminder goes out. With plain cron, 14:00 passed during the reboot and
that reminder is gone with no record it was owed.

Recovery within the hour survives; past the hour boundary it does not. Which is why T5 exists.

---

## 3. What already exists

Not to be re-done:

| Piece | Where | State |
|---|---|---|
| Compose stack | `infra/docker-compose.yml` | postgres, migrate, api, prefect-server, prefect-deploy, prefect-worker, cloudflared. Healthchecks and restart policies in place. Needs splitting (T1). |
| Backups | `infra/backup/backup.sh` | `pg_dump -Fc` → S3, day-partitioned keys, S3-compatible endpoints. DSN-driven, so it runs from anywhere. Needs count-based pruning (T4). |
| Restore | `infra/backup/restore.sh`, `docs/runbooks/backup-restore.md` | Documented; never actually executed (T8). |
| Tunnel | `infra/cloudflared/config.yml`, `docs/runbooks/cloudflare-tunnel.md` | `api.wishly.dev` → `api:8000`. |
| Pages | `docs/runbooks/cloudflare-pages.md` | Static SPA making authenticated calls through the tunnel — already the shape `ideas.md` asked for. |
| Deploy sequence | `docs/runbooks/production-deploy.md` | Accurate except for the single-host assumption. |

---

## 4. Tasks

**T1 — Split the compose files** — ✅ done
- *Scope:* `infra/vm-db/docker-compose.yml` (postgres + backup) and
  `infra/vm-wishly/docker-compose.yml` (migrate, api, prefect-server, prefect-deploy,
  prefect-worker, cloudflared). Decide whether today's `infra/docker-compose.yml` becomes the
  dev all-in-one or is retired — don't leave three files where two are true.
- *Treat vm-db like the managed database it stands in for:* no application containers on it,
  a role per consumer rather than one superuser, and connection by hostname over the VPN.
  When this becomes RDS, the app config should not need to change shape.
- *Port binding:* publish `5432` **bound to the VPN address specifically**
  (`ports: ["10.x.x.x:5432:5432"]`), not `0.0.0.0`. The default binding puts the database on
  your whole LAN, which is a different thing from "it's on my VPN". Add `pg_hba.conf` entries
  for the `vm-wishly` address only.
- *Files:* `infra/vm-db/`, `infra/vm-wishly/`, `docs/runbooks/production-deploy.md`.
- *Acceptance:* both stacks come up independently; the hourly flow runs on `vm-wishly`
  against `vm-db`.

**T2 — Prefect server state into Postgres** — ✅ database created; server not yet started
- *Depends on:* T1
- *Scope:* point the Prefect server at a `prefect` database on `vm-db` via
  `PREFECT_API_DATABASE_CONNECTION_URL` (asyncpg driver) instead of the SQLite file on the
  `wishly_prefect` volume. This is what makes `vm-wishly` stateless (§1.1); it also moves
  Prefect's run history inside the backup that T4 already takes.
- *Superseded detail:* an earlier draft created the databases via a
  `docker-entrypoint-initdb.d` script. That cannot work here — those scripts run **only** when
  PGDATA is empty, and this server was initialized before Wishly existed, so the script would
  have silently never executed. Tenant setup is a one-time `psql` run instead
  (`infra/vm-db/sql/create_tenant.sql`), guarded with `\gexec` existence checks so re-running
  it is safe.
- *Files:* `infra/postgres/init/01_databases.sql`, `infra/vm-wishly/docker-compose.yml`.
- *Acceptance:* destroy `vm-wishly` entirely, recreate it from compose + Infisical, and the
  deployment, schedule, and run history are all still there.

**T3 — Survive an ordering-dependent boot** — ✅ done (wait-for-DB in `migrate` + `prefect-server`); cold-boot test outstanding
- *Depends on:* T1
- *Scope:* the `migrate` one-shot currently relies on `depends_on: postgres condition:
  service_healthy`, which cannot span hosts. Once the DB is on another VM that guard is gone,
  and a `vm-wishly` reboot while `vm-db` is still coming up starts the API against an
  unmigrated database. Give `migrate` its own wait-for-DB retry loop and keep `api`'s
  `depends_on: migrate condition: service_completed_successfully`. The Prefect server needs
  the same patience for its own database.
- *Files:* `infra/Dockerfile.api` or an entrypoint script, `infra/vm-wishly/docker-compose.yml`.
- *Acceptance:* cold-boot both VMs in either order, and with `vm-db` deliberately delayed by
  60s — the stack converges healthy every time.

**T4 — Count-based backup retention**
- *Scope:* keep the **last 48 dumps** in S3. `backup.sh` prunes local dumps by
  `RETENTION_DAYS` and delegates remote retention to a bucket lifecycle rule, which is
  day-granular and cannot express a count. Add a prune step: list the prefix, sort by key
  (timestamps are lexicographic, so this is just `sort`), delete past the newest 48.
- *Scope:* back up **both** databases now that Prefect lives there — either a second dump or
  a cluster-wide `pg_dumpall`. Losing `prefect` costs only history, but a restore runbook that
  silently omits a database is worse than one that says so.
- *Scope:* the job runs on `vm-db`. It is DSN-driven, so it ports unchanged to running
  elsewhere when this becomes a managed database.
- *Files:* `infra/backup/backup.sh`, `infra/vm-db/docker-compose.yml`, `infra/.env.example`
  (`BACKUP_KEEP_LAST=48`), `docs/runbooks/backup-restore.md`.
- *Acceptance:* seed 50 objects under the prefix, run the prune, exactly the newest 48 remain.

**T5 — Alert on a failed or missed run**
- *Depends on:* T1
- *Scope:* nothing currently tells you when a send fails. `report_failure`
  (`flows.py:32`) logs to stdout and stops there. Because a missed hour is an unrecoverable
  missed reminder (§2.1), that hook should email you — the Resend client is already in the
  same package. Cover the run *not happening at all* too: a flow that never starts fires no
  failure hook, so add a dead-man's-switch (an external cron-monitor ping on success, alerting
  on absence) or a daily digest of the previous day's `notification_log`.
- *Files:* `backend/src/wishly/orchestration/flows.py`, `docs/runbooks/observability.md`.
- *Acceptance:* kill `vm-db`, wait for the top of the hour, receive an alert.

**T6 — Infisical agent on both VMs**
- *Scope:* use the **agent**, which renders `infra/.env` to disk and refreshes it — not an
  SDK fetch at container start. The cached file means a reboot during an Infisical Cloud
  outage still brings the stack up; fetch-at-boot would make Infisical a hard dependency of
  every restart, including the ones you do at 2am because something else broke.
- *Scope:* one machine identity per VM, scoped to that VM's secrets only. `vm-db` needs
  `POSTGRES_*` and the S3 credentials; `vm-wishly` needs Clerk, Resend, the two database
  URLs, and `TUNNEL_TOKEN`. Neither needs the other's.
- *Bootstrap caveat:* the machine identity's client secret lives on the host in plaintext.
  Unavoidable and acceptable — one credential, individually revocable, instead of the fifteen
  currently sitting in `.env`.
- *Files:* `/etc/infisical/agent.yaml` + `env.tmpl` and a systemd unit per VM (host-side, not
  in the repo); **written up in full in [runbooks/secrets.md](runbooks/secrets.md)**. Also
  update `docs/runbooks/production-deploy.md` step 1, which still says `.env` is the only
  place production secrets exist.
- *Acceptance:* rotate a secret in Infisical → agent re-renders → `docker compose up -d` picks
  it up. Then block egress to Infisical, reboot the VM, and confirm the stack still starts.

**T7 — Clean up the Infisical experiment**
- *Depends on:* T6
- *Scope:* `infra/infisical/` is a merged experiment — `get_secrets.py`, `aws_test.py`,
  `local_file.txt`, and practice backup/restore scripts hardcoded to a `wishly-dev-01` bucket
  and a `pg-backup-practice` container. Promote what T4/T6 actually use, delete the rest. The
  Mintlify docs under `infra/infisical/docs-mintlify/` should move to `docs/runbooks/` or be
  dropped — not maintained in two places.
- *Acceptance:* no dead code under `infra/infisical/`; no practice bucket names remain.

**T8 — Prove the restore**
- *Depends on:* T4
- *Scope:* actually run `restore.sh` against a scratch database from a real S3 dump. A backup
  that has never been restored is a hypothesis, and it is the only safety net in this design.
- *Files:* `docs/runbooks/backup-restore.md` — record the date last verified.
- *Acceptance:* row counts match the source; the app starts clean against the restored DB.

**T9 — Production configuration check**
- *Depends on:* T1
- *Scope:* no new infrastructure, just the settings that fail silently. `ENVIRONMENT=prod`
  (which also permanently disables `AUTH_DEV_BYPASS`); `CLERK_FRONTEND_API` set to the
  production instance host — without it every authenticated request 401s while the app
  otherwise looks fine; `ALLOWED_ORIGINS` listing **both** `https://wishly.dev` and
  `https://app.wishly.dev`, or the dashboard's calls fail CORS.
- *Acceptance:* sign in at `app.wishly.dev`, create an event, receive a real reminder email at
  the right local hour.

---

## 5. Suggested order

T1 → T3 → T9 gets you deployed and working. T2 makes `vm-wishly` disposable. T4 → T8 makes
the data recoverable — do T8 early, not last. T5 is what turns a silent failure into a known
one. T6 → T7 move the secrets, and can come first if you'd rather not hand-copy a `.env`
onto two VMs even once.

---

## 6. Environment variables

Add to PLAN.md §11.

| Variable | Used by | Notes |
|---|---|---|
| `PREFECT_API_DATABASE_CONNECTION_URL` | prefect-server | `postgresql+asyncpg://…@vm-db:5432/prefect` (T2) |
| `BACKUP_KEEP_LAST` | backup (vm-db) | `48` — count-based S3 retention |
| `ALERT_EMAIL_TO` | worker | where run-failure alerts go (T5) |
| `INFISICAL_CLIENT_ID` / `INFISICAL_CLIENT_SECRET` | agent, both VMs | per-VM machine identity; the one bootstrap secret on disk |
| `INFISICAL_PROJECT_ID` / `INFISICAL_ENV` | agent, both VMs | |

`DATABASE_URL` changes shape rather than being new: the host becomes `vm-db`'s VPN address
instead of the `postgres` compose service name. `POSTGRES_USER` / `POSTGRES_PASSWORD` /
`POSTGRES_DB` are needed only on `vm-db`. `PREFECT_API_URL` stays
`http://prefect-server:4200/api` — server and worker remain on the same VM.

---

## 7. Deliberately cut

Recorded so none of it is dropped silently:

- **TLS on the database connection.** The VPN is the trust boundary for now. Revisit before
  anyone else has an account — the connection carries Clerk user ids and email addresses in
  the clear on the wire. Add `sslmode=verify-full` then. The managed database this is
  simulating will require it anyway.
- **Invite-only signup.** Clerk signup is open; anyone with the URL can create an account.
  Fine while you are the only user and nobody has the link. It becomes the blocker the moment
  you hand the URL to someone, and the gate belongs at `api/crud.py:26` (`provision_user`),
  which every authenticated user passes through before they have a row.
- **AWS failover, RDS standby, failure-detection node.** Cut. Recovery is T8's restore
  runbook, executed by hand.
- **The webhook-ingestion Lambda.** Cut. Clerk and Resend post directly to the tunnel.
  Residual gap: `provision_user` self-heals a dropped `user.created`, but `user.updated`,
  `user.deleted`, and Resend bounce events arrive once — if the house is down past the
  providers' retry window, those are lost. Acceptable at this size.
- **A separate Prefect VM.** Server and worker both live on `vm-wishly` (§2). Revisit only if
  Prefect starts orchestrating other projects, and note that adding workers elsewhere does not
  require moving the server.
- **S3 as an application object store.** Nothing uploads files. Backups only.
- **Prefect Cloud.** Its free tier offers only managed work pools, which run on Prefect's
  infrastructure and cannot reach a Postgres with no public port — already documented in
  `infra/docker-compose.yml`. Self-hosted stays.
