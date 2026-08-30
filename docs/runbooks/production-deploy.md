# Production deploy

> **Superseded in part (2026-08-30).** This runbook describes the previous
> topology: two home VMs (`vm-wishly` + `vm-db`) with Postgres and a self-hosted
> Prefect server on Proxmox. The database has since moved to **RDS**, Prefect's
> control plane to **Prefect Cloud**, and the recovery story to an **AWS standby**
> — see [DEPLOYMENT-PLAN.md](../DEPLOYMENT-PLAN.md) for the current target and the
> tasks that get there.
>
> Still accurate and worth reading: the VM sizing rationale, the Proxmox settings,
> the Cloudflare tunnel steps, and the failure modes at the end. Treat the compose
> service list and the migration step as historical.

End-to-end order of operations for deploying Wishly onto two Proxmox VMs. Each step links
to the runbook with the detail; this page exists so the sequence and its dependencies live
in one place.

Companion to [DEPLOYMENT-PLAN.md](../DEPLOYMENT-PLAN.md), which is the *task* plan — what
has to be built. This is the *procedure* — how to stand it up once it is.

> **State check.** This describes the target topology. `infra/vm-db/` and
> `infra/vm-wishly/` are produced by plan task **T1**; until that lands, the only thing
> that exists is the single-host `infra/compose.yaml`, and steps 4–5 below do not
> have files to point at. Steps 1–3 and 6–8 are accurate either way.

---

## What runs where

| Piece | Where | Notes |
|---|---|---|
| SPA (marketing + dashboard) | Cloudflare Pages | one build, two hostnames |
| API | `vm-wishly`, `api:8000` | no published port; the tunnel reaches it |
| Prefect server + worker | `vm-wishly` | self-hosted — see "Why not Prefect Cloud" |
| `cloudflared` | `vm-wishly` | outbound only; no inbound ports anywhere |
| Postgres 18.4 | `vm-db` | `wishly` + `prefect` databases |
| Backups | `vm-db` → S3 | hourly, last 48 dumps |
| Secrets | Infisical Cloud → agent on each VM | renders `infra/.env` |
| Auth | Clerk | production instance |
| Email | Resend | verified sending domain |

`vm-db` is a **general Postgres host**, deliberately treated like the managed database it
will eventually be: no application containers on it, a role per consumer, reached by
hostname over the VPN. `vm-wishly` holds no durable state — Prefect's state lives in
Postgres — so it can be destroyed and rebuilt from compose + Infisical at any time.

---

## VM specifications

| | `vm-wishly` | `vm-db` |
|---|---|---|
| vCPU | 2 | 2 |
| RAM | **4 GB** | **4 GB** |
| Disk | 40 GB | 60 GB |
| Swap | 2 GB | 2 GB |
| OS | Ubuntu Server 24.04 LTS | Ubuntu Server 24.04 LTS |

**Why 4 GB on `vm-wishly`:** steady state is ~1.1–1.6 GB — `prefect-server` 400–600 MB,
`prefect-worker` 200–300 MB, `api` 150–250 MB, `cloudflared` 30–50 MB, Infisical agent
~25 MB, OS + Docker daemon 300–400 MB. The headroom is for `docker build`, which spikes
1–2 GB while `uv sync` runs. Running tight means the OOM killer reaps `prefect-server`,
and a Prefect server that dies at the top of the hour costs you reminders silently.

**Lean variant:** if images are built in CI and pulled from a registry rather than built on
the box, 2 GB / 2 vCPU / 20 GB is genuinely enough.

**Why 60 GB on `vm-db`:** Wishly's data is tiny, but this is the general database host —
the disk is for future tenants, WAL, and local dump staging. Set `shared_buffers` ≈ 1 GB.

### Proxmox settings that matter more than the numbers

- **CPU type `host`**, not `kvm64` — a large difference for Python process startup.
- **VirtIO SCSI single** controller; disk on `scsi0` with `discard=on` (thin provisioning
  actually reclaims space).
- **Disable ballooning on `vm-db`.** Postgres wants stable memory. Fine to leave enabled on
  `vm-wishly`.
- **Install `qemu-guest-agent`** in both guests so PVE gets clean shutdowns and IP reporting.
- **Start at boot** enabled on both, with a **boot delay on `vm-wishly`** so `vm-db` leads.
  This is a convenience, not a correctness guarantee — see step 5.
- Both VMs on the **private VLAN**. Only `vm-wishly` needs egress to the internet
  (Cloudflare, Clerk, Resend, Infisical); `vm-db` needs egress only to S3 and Infisical.

---

## 1. Pre-flight — accounts and secrets

Nothing here needs a host. Collect it all first; every later step blocks on it.

1. **Clerk production instance.** Note `sk_live_…`, `pk_live_…`, the **Frontend API host**
   (`CLERK_FRONTEND_API`, e.g. `https://clerk.wishly.dev`), and a webhook signing secret.
   Register **both** `wishly.dev` and `app.wishly.dev` on the instance. Configure the
   session-token claim from PLAN §10 — without the `email` claim the API rejects every
   token as missing identity claims.
2. **Resend.** Verify the sending domain, add SPF/DKIM/DMARC — see
   [resend-domain.md](resend-domain.md). Note `RESEND_API_KEY` and a webhook signing secret.
3. **Bucket for backups.** AWS S3 or Cloudflare R2, plus an access key scoped to it.
4. **Cloudflare Tunnel token** — see [cloudflare-tunnel.md](cloudflare-tunnel.md).
5. **Infisical project** `wishly`, environment `prod`. Load every value above into it, and
   create the two machine identities — see [secrets.md](secrets.md) §2.

`CLERK_FRONTEND_API` is not optional. The API verifies tokens against that origin's JWKS,
and without it every authenticated request returns 401 while the app otherwise looks fine.

---

## 2. Provision both VMs

Per the specs above. Then on each:

```bash
sudo apt-get update && sudo apt-get install -y qemu-guest-agent
sudo install -m 0755 -d /etc/apt/keyrings   # Docker's official install steps
# ... install docker-ce + docker-compose-plugin ...
sudo usermod -aG docker "$USER"   # log out and back in
docker --version && docker compose version
```

Confirm the private network before going further:

```bash
# from vm-wishly
ping -c1 <vm-db-address>
```

---

## 3. Infisical agent on both VMs

Do this **before** bringing up either stack, so no `.env` is ever hand-copied onto a host.

Full procedure in [secrets.md](secrets.md) — machine identity per VM, bootstrap credentials
at `/etc/infisical/`, `agent.yaml` + `env.tmpl`, and the systemd units.

Verify on each VM before continuing:

```bash
sudo systemctl status infisical-agent
sudo test -s /opt/wishly/infra/.env && echo "env rendered"
```

If `.env` is empty or missing, stop here. Everything downstream fails in confusing ways —
Compose starts with an empty environment and the API comes up looking healthy while
401ing every request.

---

## 4. `vm-db` — Postgres and backups

```bash
cd /opt/wishly/infra/vm-db
docker compose up -d
docker compose ps
```

First init creates the `wishly` and `prefect` databases and their roles from
`infra/postgres/init/`. Confirm both exist:

```bash
docker compose exec postgres psql -U postgres -c '\l' | grep -E 'wishly|prefect'
```

Check that Postgres is bound to the **VPN address only** — not `0.0.0.0`, which would put
the database on your whole LAN:

```bash
ss -tlnp | grep 5432        # expect the VPN address, not 0.0.0.0
```

Then start the backup job and let one cycle run:

```bash
docker compose up -d backup
docker compose logs -f backup
```

---

## 5. `vm-wishly` — the application stack

```bash
cd /opt/wishly/infra/vm-wishly
docker compose up -d --build
docker compose ps
```

Order within the VM is enforced by health conditions: `migrate` runs Alembic to head and
exits → `api` starts → `cloudflared` waits for the API's health check. `prefect-deploy`
creates the work pool and publishes the hourly deployment once `prefect-server` is healthy.

**The cross-VM order is not enforced by anything.** Compose's `depends_on: postgres
condition: service_healthy` cannot span hosts, so a `vm-wishly` reboot while `vm-db` is
still coming up will start `migrate` against an unreachable database. Plan task **T3** adds
a wait-for-DB retry loop; until it lands, bring the VMs up in order by hand and treat the
PVE boot delay as a convenience rather than a guarantee.

Verify:

```bash
docker compose logs api | tail
curl -sf http://localhost:8000/health
curl -sf http://localhost:8000/ready        # 503 if Postgres is unreachable
curl -sf http://localhost:4200/api/health   # prefect server, host-local
```

The Prefect UI is on `4200`, bound to the VPN. Browse it from a machine on the VPN — it has
no authentication of its own, so it must never be published publicly.

---

## 6. Tunnel

Follow [cloudflare-tunnel.md](cloudflare-tunnel.md) to route `api.wishly.dev` to
`http://api:8000`. Then, from off the host:

```bash
curl -i https://api.wishly.dev/health
```

The tunnel ingress is an allowlist with a `http_status:404` catch-all, so nothing but the
API is reachable even if something else is listening.

---

## 7. Frontend

Follow [cloudflare-pages.md](cloudflare-pages.md). Set the build environment variables
there — including `VITE_APP_BASE_URL=https://app.wishly.dev` — and add both custom domains.

The production build **refuses to start** if `VITE_DEV_NO_AUTH` or `VITE_MOCK_API` is
`true`, or if the Clerk key is missing or still the placeholder. That guard exists because
such a build looks completely normal while bypassing auth entirely.

---

## 8. Webhooks

With `api.wishly.dev` live, register both:

- Clerk → `https://api.wishly.dev/webhooks/clerk` (user sync)
- Resend → `https://api.wishly.dev/webhooks/resend` (bounces → suppression)

Put each signing secret in **Infisical**, not in a file on the host. The agent re-renders
and restarts the API within its poll interval.

---

## Post-deploy checks

- [ ] `https://wishly.dev` loads; `https://app.wishly.dev` loads the dashboard
- [ ] Sign-up works and lands on onboarding; the user row appears in `wishly.users`
- [ ] `https://api.wishly.dev/health` returns 200 from off-host
- [ ] `ss -tlnp` on `vm-db` shows 5432 on the VPN address, never `0.0.0.0`
- [ ] Prefect UI shows `hourly-send` with an active schedule and a healthy worker
- [ ] One flow run completes — trigger it manually rather than waiting for the hour
- [ ] A test reminder email arrives and renders
- [ ] A dump has landed in the bucket **and a restore of it has been tried**
      ([backup-restore.md](backup-restore.md)) — a backup never restored is a hypothesis,
      and it is the only recovery path in this design
- [ ] Rebuild check: `docker compose down` on `vm-wishly`, destroy and recreate the VM, and
      confirm the deployment, schedule, and run history all survive (they live in `vm-db`)
- [ ] `docker compose logs` on both VMs is free of stack traces

---

## Settings that fail silently

The three that produce a working-looking deployment that is subtly broken:

| Setting | Symptom if wrong |
|---|---|
| `ENVIRONMENT=prod` | Also permanently disables `AUTH_DEV_BYPASS`. Note `infra/.env.example` ships `dev` — the interlock is disarmed unless you set this. |
| `CLERK_FRONTEND_API` | Every authenticated request 401s; the SPA renders normally and looks like a backend outage. |
| `ALLOWED_ORIGINS` | Must list **both** `https://wishly.dev` and `https://app.wishly.dev`, or the dashboard's API calls fail CORS. |

---

## Known gaps

Recorded in [DEPLOYMENT-PLAN.md](../DEPLOYMENT-PLAN.md) §7 and repeated here because they
affect operating the thing:

- **No TLS on the database connection.** The VPN is the trust boundary. The wire carries
  Clerk user ids and email addresses in the clear.
- **Signup is open.** Anyone with the URL can create an account.
- **No alerting on a failed or missed run** until plan task T5. A missed hour is an
  unrecoverable missed reminder, and nothing currently tells you it happened.
- **Recovery is manual** — restore from S3 by hand, per [backup-restore.md](backup-restore.md).

---

## Prefect Cloud and the work-pool limit

Worth recording, because it is the constraint that shaped the orchestration setup.

Prefect Cloud's free plan offers **no custom work pools** — creating a `process`,
`docker`, or `kubernetes` pool returns *"Your plan does not support hybrid or push work
pools."* Its managed pools execute flows on Prefect's own infrastructure, which cannot
reach a Postgres that publishes no public port. That ruled out the work-pool-and-worker
model on the free tier, and a self-hosted Prefect server was the answer for a while.

**`serve()` sidesteps the limit**, which is why the stack now uses it.
`flow.to_deployment(...)` plus `serve(...)` registers a deployment and runs it from a
long-lived local process; it creates no work pool and needs no worker, so the plan
restriction above does not apply to it. `PREFECT_API_URL` + `PREFECT_API_KEY` point at the
Cloud workspace, and the flow still executes here, next to the database.

**If Cloud refuses the deployment** (a tier limit tightening, or exceeding the free plan's
deployment cap), the fallback is one step: add a `prefect-server` service back to
`infra/compose.yaml`, give it a `prefect` database, and point `PREFECT_API_URL` at
`http://prefect-server:4200/api`. Nothing in the flow code changes — `serve()` talks to
whichever API it is pointed at.
