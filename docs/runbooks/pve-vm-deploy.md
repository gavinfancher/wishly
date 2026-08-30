# Moving Wishly from the Mac to a PVE VM

Takes the dev deployment off the workstation and onto a Proxmox VM, against RDS.
Same role the Mac holds today — dev Clerk instance, the `api-dev.wishly.dev`
tunnel, `ENVIRONMENT=dev` — on hardware that does not sleep or travel.

Production (`ENVIRONMENT=prod`, the production Clerk instance, `api.wishly.dev`)
is a later step: **T9** in [DEPLOYMENT-PLAN.md](../DEPLOYMENT-PLAN.md).

Related: [secrets.md](secrets.md) for the Infisical model,
[aws-vpc-tailscale.md](aws-vpc-tailscale.md) for the network this plugs into.

---

## What actually changes

Less than it looks. The application is unchanged; four things move.

| | Mac (today) | PVE VM |
|---|---|---|
| Database | Postgres container (`compose.local.yaml`) | **RDS**, over the tailnet |
| Compose files | `compose.yaml` + `compose.local.yaml` | `compose.yaml` **only** |
| Secrets | `up.sh`, one-shot, run by hand | `infisical-agent.service`, polling |
| Template | `env.mac.tmpl` | `env.vm.tmpl` |

The single most common mistake here is bringing `compose.local.yaml` along out of
habit. That overlay exists to add a Postgres container; on this host it would
start a second, empty database and quietly point the app at it. `reload.sh` never
passes it, and neither should you.

### Do not copy images from the Mac

Your Mac is `arm64`; the VM is `amd64`. Nothing in the Dockerfiles pins a
platform, so images build for whatever host builds them. **Build on the VM.**
`docker save`/`load` from the laptop produces images that will not run.

---

## Step 1 — The VM

Ubuntu 24.04 LTS on PVE. **2 vCPU / 2 GB RAM / 20 GB disk** is enough now: the
stack is three containers (`api`, `worker`, `cloudflared`) and no database.

Give it 4 GB if you intend to build images on it regularly — `uv sync` spikes to
1–2 GB during a build, and the OOM killer reaping a build is a confusing failure.
[production-deploy.md](production-deploy.md) has the Proxmox settings; ignore its
two-VM structure, which is superseded.

```bash
sudo apt update && sudo apt install -y ca-certificates curl git
# Docker Engine + compose plugin, from Docker's own repo (not Ubuntu's docker.io)
curl -fsSL https://get.docker.com | sudo sh
sudo systemctl enable --now docker
docker compose version          # expect v2.x
```

## Step 2 — Join the tailnet, and prove RDS is reachable

This is the step that actually unlocks the database. The `wishly-vpc-router` EC2
advertises `10.0.0.0/16` to the tailnet (see
[aws-vpc-tailscale.md](aws-vpc-tailscale.md)); without `--accept-routes` this VM
simply cannot see RDS, and every later step fails in a way that looks like a
Postgres problem.

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --accept-routes --hostname=wishly-vm
```

**Verify before continuing.** Do not proceed on faith:

```bash
tailscale status | grep -i router          # the subnet router should be listed
ip route | grep 10.0                       # the advertised route should be present
sudo apt install -y postgresql-client
psql "postgresql://<master>@<rds-endpoint>:5432/postgres?sslmode=require" -c 'select 1'
```

If `psql` hangs rather than erroring, the route is missing — check that the route
is **approved** in the Tailscale admin console, not merely advertised.

## Step 3 — Bootstrap the database (once, from anywhere on the tailnet)

Skip if you have already done this. Both files are idempotent.

```bash
psql "$ADMIN_DATABASE_URL" -v ON_ERROR_STOP=1 \
  -v wishly_password="'<pick-one>'" -f infra/sql/create_tenant.sql

psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f infra/sql/schema.sql
```

`DATABASE_URL` here is the `wishly` role, not the master user, and it **must**
carry `?sslmode=require` — the parameter group sets `rds.force_ssl=1`, so a plain
DSN is refused at connect time.

The `schema` service in `compose.yaml` also applies `schema.sql` on every `up`,
so this is belt-and-braces. Doing it by hand first means a schema error surfaces
now, with a readable `psql` message, instead of inside a container log.

## Step 4 — A machine identity for this VM

One per host ([secrets.md §2](secrets.md)). Do **not** reuse the Mac's: the point
is that a compromised host is one revocation, not a shared credential.

In Infisical → Access Control → Machine Identities → Create, **Universal Auth**,
read-only on the `dev` environment of the `wishly` project. It needs:

```
DATABASE_URL  TUNNEL_TOKEN  PREFECT_API_URL  PREFECT_API_KEY
CLERK_SECRET_KEY  CLERK_WEBHOOK_SIGNING_SECRET
RESEND_API_KEY  RESEND_WEBHOOK_SIGNING_SECRET
```

Everything else is a literal in `env.vm.tmpl`.

**`DATABASE_URL` in Infisical must be the RDS DSN with `?sslmode=require`.** It is
a secret rather than a literal because it carries the password — and because a
literal would silently *win* over the Infisical value, since literals render after
the secret loop and Compose takes the last duplicate key. That failure is
invisible: the stack comes up pointed at the wrong database and looks healthy.

Write the credentials with `printf`, never `echo`:

```bash
sudo mkdir -p /etc/infisical
printf '%s' '<client-id>'     | sudo tee /etc/infisical/wishly-client-id     >/dev/null
printf '%s' '<client-secret>' | sudo tee /etc/infisical/wishly-client-secret >/dev/null
sudo chmod 0600 /etc/infisical/wishly-*
```

`echo` appends a newline, the newline is sent as part of the credential, and
authentication fails with an error that does not mention whitespace.

## Step 5 — Put the repo on the VM and build once

```bash
sudo git clone https://github.com/gavinfancher/wishly.git /opt/wishly
cd /opt/wishly
sudo git checkout rearchitect-rds-prefect-cloud   # until it is merged
```

Install the Infisical CLI, then render `.env` once by hand so you can inspect it
before anything starts:

```bash
curl -1sLf https://artifacts-cli.infisical.com/setup.deb.sh | sudo -E bash
sudo apt install -y infisical

sudo infisical agent --config /opt/wishly/infra/infisical/agent.vm.yaml &
sleep 10 && sudo kill %1
sudo grep -oE '^[A-Z_]+=' /opt/wishly/infra/.env | sort   # keys only, no values
```

Then the first build, by hand — it takes minutes and would blow the agent's
600s `execute` timeout on a slow VM:

```bash
cd /opt/wishly
sudo docker compose -f infra/compose.yaml --env-file infra/.env up -d --build
sudo docker compose -f infra/compose.yaml ps
sudo docker compose -f infra/compose.yaml logs schema     # should end "schema applied"
curl -fsS localhost:8000/ready                            # not published in prod compose; see note
```

`compose.yaml` publishes no ports, so `/ready` is only reachable from inside the
network. Check it with
`sudo docker compose -f infra/compose.yaml exec api python -c "import urllib.request;print(urllib.request.urlopen('http://localhost:8000/ready').read())"`.

## Step 6 — Hand it to systemd

Three units: the agent renders the file, and a path watcher reloads the stack
when it changes.

```bash
sudo cp /opt/wishly/infra/systemd/infisical-agent.service /etc/systemd/system/
sudo cp /opt/wishly/infra/systemd/wishly-reload.{path,service} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now infisical-agent wishly-reload.path
journalctl -u infisical-agent -u wishly-reload -f
```

You should see the agent authenticate and render, then `wishly-reload` report the
key list followed by `docker compose up -d`. From there a secret rotated in
Infisical reaches the stack within the 60s poll interval.

**Why a path unit rather than the agent's own hook.** The agent supports an
`execute` block that is meant to run a command after each render. It does not run
on the CLI build here (0.43.128): the render succeeds, the log looks healthy, and
the command is silently never invoked — verified with a probe command that never
fired, both nested under `config` and as a sibling of it. Watching the file from
outside is independent of that, and its output goes to the journal under its own
unit instead of disappearing.

`systemctl is-active` is not a health check for the agent. `Restart=always` means
a unit that cannot even exec its binary still reports `active` while flapping.
Read the journal.

There is no unit for Compose itself. The containers carry
`restart: unless-stopped`, so Docker restores them after a reboot on its own.

## Step 7 — Cut over

Two things must not run in both places at once. Neither corrupts data —
`notification_log`'s unique constraint makes a double send impossible either way
— but both produce nondeterministic behaviour that is miserable to debug.

**The tunnel.** Two `cloudflared` instances sharing one `TUNNEL_TOKEN` both
register, and Cloudflare load-balances between them. Requests would land on the
Mac or the VM at random.

**The send pipeline.** Two `serve()` processes on the same Prefect Cloud
deployment both poll, and either may claim a run.

So, on the Mac:

```bash
docker compose -f infra/compose.yaml -f infra/compose.local.yaml down
```

Then confirm the VM is serving alone:

```bash
curl -fsS https://api-dev.wishly.dev/health          # answered by the VM now
```

In Prefect Cloud, the deployment should show exactly one healthy runner. Trigger
`preview-reminder` with `send=false` — it renders from real rows without touching
Resend, which proves database, rendering, and the Prefect round-trip in one go.

## Rollback

Nothing was destroyed, so this is just reversing step 7:

```bash
# On the VM
sudo systemctl stop infisical-agent
cd /opt/wishly && sudo docker compose -f infra/compose.yaml down

# On the Mac
./infra/infisical/up.sh
```

RDS keeps whatever the VM wrote, and the Mac's local Postgres still holds its own
data — they are separate databases, so a rollback means the Mac sees its old
rows, not the VM's. Worth knowing before you assume the two are interchangeable.

---

## Failure modes worth recognising

| Symptom | Cause |
|---|---|
| `psql` hangs against RDS | Route advertised but not **approved** in the Tailscale console |
| `no pg_hba.conf entry` / SSL error | `DATABASE_URL` missing `?sslmode=require`; `rds.force_ssl=1` |
| Agent auth fails, credential "looks right" | `echo` used instead of `printf` — trailing newline in the file |
| Stack healthy but every request 401s | `CLERK_FRONTEND_API` unset or pointing at the wrong instance |
| SPA calls fail in the browser, API fine via curl | `ALLOWED_ORIGINS` missing an origin — CORS |
| cloudflared up, hostname 502s | `TUNNEL_TOKEN` shadowed by an empty literal, or the Mac still running |
| App healthy against an empty database | `compose.local.yaml` included by mistake — you are on a container, not RDS |
| Image runs on the Mac, exits instantly on the VM | Copied an `arm64` image; rebuild on the VM |
