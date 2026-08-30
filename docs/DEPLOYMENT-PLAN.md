# Wishly — Deployment Plan

Companion to [PLAN.md](PLAN.md), which covers building the product. This file
covers **getting it deployed, keeping the data safe, and surviving the house
going dark.**

Rewritten 2026-08-30, when the target moved from two home VMs with a local
Postgres to **RDS plus an AWS standby**. The previous revision listed AWS
failover as deliberately cut; it is now the point.

---

## 1. Target

```
   Browser
      │  HTTPS
      ▼
   Cloudflare edge
      ├── Pages ──────── wishly.dev, app.wishly.dev   (static SPA)
      │
      └── api.wishly.dev
             │  Cloudflare Tunnel  ── follows whichever host is running ──┐
             ▼                                                            │
   ┌─── Proxmox VE (home) ─────────────┐        ┌─── AWS ─────────────────┴────┐
   │                                   │        │                              │
   │  vm-wishly (normal operation)     │        │  standby EC2 (stopped)       │
   │  ┌──────────────────────────┐     │        │  ┌────────────────────────┐  │
   │  │ cloudflared              │     │        │  │ same compose stack,    │  │
   │  │ api:8000                 │     │        │  │ pre-configured, off    │  │
   │  │ worker (Prefect serve)   │     │        │  └────────────────────────┘  │
   │  └──────────────────────────┘     │        │                              │
   │            │                      │        │  watchdog VM (t4g.nano)      │
   └────────────┼──────────────────────┘        │  ┌────────────────────────┐  │
                │                               │  │ polls PVE via Tailscale│  │
                │        Tailscale VPN          │  │ 3 strikes → start EC2  │  │
                └───────────────┬───────────────┤  └────────────────────────┘  │
                                │               │                              │
                                ▼               │  ┌────────────────────────┐  │
                        ┌───────────────┐       │  │ RDS Postgres (wishly)  │  │
                        │  RDS Postgres │◄──────┼──┤ private subnet, no     │  │
                        └───────────────┘       │  │ public endpoint        │  │
                                                │  └────────────────────────┘  │
                                                └──────────────────────────────┘

   Prefect Cloud ──── schedule + run history + UI (control plane only)
   Infisical Cloud ──agent──► renders infra/.env on each host
   Clerk (auth) · Resend (email) · S3 (logical backups)
```

**The database is no longer at home.** That is the change everything else follows
from. Both the home host and the standby EC2 are stateless application hosts
pointed at the same RDS instance, so a failover moves compute only — there is no
data to promote, replicate, or reconcile.

Networking for the VPC, subnets, Tailscale subnet router, and the RDS endpoint is
already written up in **[runbooks/aws-vpc-tailscale.md](runbooks/aws-vpc-tailscale.md)**.

### 1.1 Why the control plane is not at home

Prefect Cloud holds the schedule, run history, and UI; the `worker` container
calls `serve()` against it and executes flows locally. This split is what makes
the standby worth having.

A scheduler running on the home host would go down with the home host. The
watchdog would start EC2, and nothing would tell it that a 14:00 run was owed.
With Cloud, the schedule outlives the outage: the standby comes up, serves the
same two deployments, and picks up the late run.

### 1.2 What a failover actually is

1. The watchdog stops seeing the Proxmox node on the tailnet (§4, T2).
2. It starts the pre-configured EC2 instance.
3. That instance boots the same `infra/compose.yaml`, renders `infra/.env` from
   Infisical, and connects to the same RDS.
4. `cloudflared` there registers the tunnel, and `api.wishly.dev` follows.
5. Prefect Cloud hands the standby's worker any runs that went unclaimed.

Nothing is promoted and no data moves, because the only stateful component never
went down.

---

## 2. How the send pipeline fits

Worth stating explicitly, because "Prefect" usually implies more moving parts
than are here.

**One container.** `python -m wishly.orchestration.flows` calls Prefect's
`serve()`, which registers both deployments with their schedules against
`PREFECT_API_URL` and then runs their flow runs in subprocesses of that same
container. There is no work pool, no separate worker process, and no
`prefect.yaml` — those exist for dynamically scheduling flows across
infrastructure, which is not what one hourly cron needs.

| Deployment | Schedule | Purpose |
|---|---|---|
| `hourly-send` | `0 * * * *` | Finds reminders due this hour and sends each exactly once. |
| `preview-reminder` | none (manual) | Renders a real email for an event that is not due yet. `send=False` by default, so triggering it with stock parameters touches nothing. |

The flow code ships **inside the worker image**, so changing anything under
`orchestration/` means rebuilding and restarting that container.

### 2.1 Why Prefect rather than cron

For a single hourly tick, `cron` calling `python -m wishly.orchestration.flows --once`
would work, and that flag exists for exactly that fallback.

Prefect earns its place because of one property of the send logic:
`due.py:46` gates on `local_now(...).hour == send_hour`, evaluated at execution
time. The send window is one hour wide, and **a missed tick is a permanently lost
reminder** — the next hour no longer matches that user's `send_hour`, and there is
no catch-up pass.

A run scheduled at 14:00 that nothing claims sits in `Late` rather than
evaporating, so a worker that comes back at 14:20 still executes it, the local
hour is still 14, and the reminder goes out.

**Recovery within the hour survives; past the hour boundary it does not.** A
failover that takes longer than the remainder of the hour still loses that hour's
reminders. Closing that gap means widening the due check (see T7), not adding
infrastructure.

---

## 3. What already exists

Not to be re-done:

| Piece | Where | State |
|---|---|---|
| Compose stack | `infra/compose.yaml` | schema one-shot, api, worker, cloudflared. Healthchecks and restart policies in place. |
| Schema | `infra/sql/schema.sql` | Whole schema in one idempotent file; the test suite builds from it, so drift from the models fails the tests. |
| DB bootstrap | `infra/sql/create_tenant.sql` | Creates the `wishly` role + database on a new server. |
| Backups | `infra/backup/backup.sh` | `pg_dump -Fc` → S3, day-partitioned keys. DSN-driven, so it runs unchanged against RDS. Needs count-based pruning (T5). |
| Restore | `infra/backup/restore.sh`, `runbooks/backup-restore.md` | Documented; never actually executed (T8). |
| VPC / Tailscale / RDS | `runbooks/aws-vpc-tailscale.md` | VPC, subnets, subnet router, private RDS endpoint. |
| Watchdog | `infra/failover/detection-script/` | Polls a Tailscale device's `lastSeen`; exits 1 after 3 consecutive stale checks. Needs the EC2 start wired to that exit (T2). |
| Tunnel | `infra/cloudflared/config.yml`, `runbooks/cloudflare-tunnel.md` | `api.wishly.dev` → `api:8000`. |
| Pages | `runbooks/cloudflare-pages.md` | Static SPA calling the API through the tunnel. |

---

## 4. Tasks

**T1 — Point production at RDS**
- *Scope:* `DATABASE_URL` becomes the RDS endpoint over the VPN. Run
  `create_tenant.sql` as the master user, then `schema.sql` as `wishly`. Retire the
  local Postgres container on the home host — `compose.local.yaml` keeps one for
  development, and that is the only place it should exist now.
- *Scope:* turn on **TLS to the database**, which the previous design deferred.
  RDS supports it out of the box and the connection carries Clerk user ids and
  email addresses. Append `?sslmode=verify-full` and ship the RDS CA bundle.
- *Acceptance:* the home stack comes up against RDS; `GET /ready` returns 200;
  an event created through the UI appears in RDS.

**T2 — Wire the watchdog to the standby**
- *Depends on:* T1
- *Scope:* the detector already exits 1 after three consecutive stale checks and
  treats an API failure as *unknown* rather than down. What is missing is the
  action. Wrap it in a systemd unit with `OnFailure=` pointing at a one-shot that
  calls `aws ec2 start-instances`, or have the script call boto3 directly.
- *Scope:* the watchdog needs an IAM role limited to `ec2:StartInstances` on the
  one standby instance ARN — not `ec2:*`, and not a user with static keys.
- *Guard:* the standby must be safe to start **while home is still up**. Two
  `cloudflared` instances for one tunnel both register, and requests land on
  whichever answers; two workers on the same Prefect deployment both poll. The
  send stays correct either way — `notification_log`'s unique constraint makes a
  double send structurally impossible — but decide deliberately whether the
  standby is additive or exclusive, and write it down.
- *Files:* `infra/failover/detection-script/`, a systemd unit, `runbooks/failover.md` (new).
- *Acceptance:* power off the Proxmox node; within `INTERVAL × THRESHOLD` plus
  boot time, `api.wishly.dev` answers from EC2 and the hourly flow runs there.

**T3 — Prove the standby without an outage**
- *Depends on:* T2
- *Scope:* a documented drill that does not require pulling the plug: start the
  standby by hand, confirm it serves and sends, stop it again. A failover path
  that has only ever been reasoned about is a hypothesis.
- *Acceptance:* recorded date of last successful drill in `runbooks/failover.md`.

**T4 — Infisical agent on both hosts**
- *Scope:* use the **agent**, which renders `infra/.env` to disk and refreshes it —
  not an SDK fetch at container start. The cached file means a reboot during an
  Infisical outage still brings the stack up; fetch-at-boot would make Infisical a
  hard dependency of every restart, including the ones at 2am because something
  else broke.
- *Scope:* one machine identity per host, scoped to that host's secrets. The
  standby EC2 needs the same set as the home host — that is what "pre-configured"
  has to mean, or the failover stops to ask for secrets.
- *Bootstrap caveat:* the machine identity's client secret lives on the host in
  plaintext. Unavoidable and acceptable — one credential, individually revocable,
  instead of the fifteen otherwise sitting in `.env`.
- *Files:* host-side agent config + systemd unit; written up in
  [runbooks/secrets.md](runbooks/secrets.md).
- *Acceptance:* rotate a secret in Infisical → agent re-renders → `docker compose up -d`
  picks it up. Then block egress to Infisical, reboot, and confirm the stack still starts.

**T5 — Count-based backup retention**
- *Scope:* keep the **last 48 dumps** in S3. `backup.sh` prunes local dumps by
  `RETENTION_DAYS` and delegates remote retention to a bucket lifecycle rule,
  which is day-granular and cannot express a count. Add a prune step: list the
  prefix, sort by key (timestamps are lexicographic, so this is just `sort`),
  delete past the newest 48.
- *Note:* RDS automated snapshots are **not** a replacement. A snapshot can only
  be restored inside the same AWS account; a `pg_dump` in a bucket restores onto
  any Postgres, including a laptop. Keep both.
- *Files:* `infra/backup/backup.sh`, `infra/.env.example` (`BACKUP_KEEP_LAST=48`),
  `runbooks/backup-restore.md`.
- *Acceptance:* seed 50 objects under the prefix, run the prune, exactly the newest 48 remain.

**T6 — Alert on a failed or missed run**
- *Scope:* nothing currently tells you when a send fails. `report_failure`
  (`flows.py:33`) logs to stdout and stops there. Because a missed hour is an
  unrecoverable missed reminder (§2.1), that hook should email you — the Resend
  client is already in the same package.
- *Scope:* cover the run *not happening at all*. A flow that never starts fires no
  failure hook. Prefect Cloud automations can alert on a late or missing run
  without any extra infrastructure, which is the cheapest version of this.
- *Files:* `backend/src/wishly/orchestration/flows.py`, `runbooks/observability.md` (new).
- *Acceptance:* revoke the Resend key, wait for the top of the hour, receive an alert.

**T7 — Make a missed hour recoverable**
- *Scope:* the one real fragility left. `due.py:46` requires the local hour to
  equal `send_hour` exactly, so any gap longer than the rest of that hour silently
  drops those reminders — including a failover that takes 20 minutes at :50.
  Widen the check to "at or after `send_hour`, and not already sent today", leaning
  on `notification_log`'s unique constraint, which already makes a repeat send
  impossible. A catch-up then costs nothing and needs no new infrastructure.
- *Files:* `backend/src/wishly/orchestration/due.py`, `backend/tests/test_due.py`.
- *Acceptance:* a run at 16:00 sends a reminder whose `send_hour` is 14 and which
  was never sent; a second run at 17:00 sends nothing.

**T8 — Prove the restore**
- *Depends on:* T5
- *Scope:* actually run `restore.sh` against a scratch database from a real S3
  dump. A backup that has never been restored is a hypothesis, and it is the only
  safety net that survives losing the AWS account.
- *Acceptance:* row counts match the source; the app starts clean against the
  restored database. Record the date last verified in `runbooks/backup-restore.md`.

**T9 — Production configuration check**
- *Scope:* no new infrastructure, just the settings that fail silently.
  `ENVIRONMENT=prod` (which also permanently disables `AUTH_DEV_BYPASS`);
  `CLERK_FRONTEND_API` set to the production instance host — without it every
  authenticated request 401s while the app otherwise looks fine; `ALLOWED_ORIGINS`
  listing **both** `https://wishly.dev` and `https://app.wishly.dev`, or the
  dashboard's calls fail CORS.
- *Acceptance:* sign in at `app.wishly.dev`, create an event, receive a real
  reminder email at the right local hour.

---

## 5. Suggested order

T1 → T9 gets you running on RDS. T2 → T3 is the failover, and T3 matters more than
it looks: an untested standby is a story, not a capability. T5 → T8 makes the data
recoverable — do T8 early, not last. T6 turns a silent failure into a known one,
and T7 removes the reason a slow failover still costs reminders. T4 can come first
if you would rather not hand-copy a `.env` onto two hosts even once.

---

## 6. Environment variables

| Variable | Used by | Notes |
|---|---|---|
| `DATABASE_URL` | api, worker, backup | Now the RDS endpoint over the VPN; add `?sslmode=verify-full` (T1) |
| `PREFECT_API_URL` / `PREFECT_API_KEY` | worker | Prefect Cloud workspace + key |
| `BACKUP_KEEP_LAST` | backup | `48` — count-based S3 retention (T5) |
| `ALERT_EMAIL_TO` | worker | where run-failure alerts go (T6) |
| `TAILSCALE_API_KEY` / `TAILSCALE_DEVICE_ID` | watchdog | the node it watches |
| `SLACK_WEBHOOK_URL` | watchdog | optional; absence only skips the alert |
| `INFISICAL_CLIENT_ID` / `INFISICAL_CLIENT_SECRET` | agent, both hosts | per-host machine identity |
| `INFISICAL_PROJECT_ID` / `INFISICAL_ENV` | agent, both hosts | |

`POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` are needed **only** by the
development Postgres in `compose.local.yaml`.

---

## 7. Deliberately cut

Recorded so none of it is dropped silently:

- **A multi-AZ or replicated database.** Single-AZ RDS with automated snapshots.
  An AZ outage is an outage; the recovery is T8's restore, by hand.
- **Automatic failback.** When home returns, moving back is manual and deliberate.
  Automating both directions is how you get a flapping pair.
- **Invite-only signup.** Clerk signup is open; anyone with the URL can create an
  account. Fine while nobody has the link. The gate belongs at
  `api/deps.py:provision_user`, which every authenticated user passes through
  before they have a row.
- **The webhook-ingestion Lambda.** Clerk and Resend post directly to the tunnel.
  Residual gap: `provision_user` self-heals a dropped `user.created`, but
  `user.updated`, `user.deleted`, and Resend bounce events arrive once — if both
  hosts are down past the providers' retry window, those are lost.
- **A self-hosted Prefect server.** Cloud's free tier covers two deployments, and
  §1.1 is the reason to keep the control plane off the hosts that fail.
- **S3 as an application object store.** Nothing uploads files. Backups only.
