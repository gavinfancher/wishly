# Secrets — Infisical Cloud + agent

How production secrets get from Infisical Cloud onto the hosts that run Wishly.
Implements T4 of [DEPLOYMENT-PLAN.md](../DEPLOYMENT-PLAN.md).

> **The Linux agent files now exist in the repo:**
> `infra/infisical/agent.vm.yaml` (long-running daemon),
> `infra/infisical/env.vm.tmpl` (RDS, no local Postgres),
> `infra/infisical/reload.sh` (validates the render before reloading), and
> `infra/systemd/infisical-agent.service`. The install procedure is
> [pve-vm-deploy.md](pve-vm-deploy.md); this page is the model behind it.
>
> **Host names changed (2026-08-30).** This was written for the two home VMs
> `vm-wishly` and `vm-db`. The database is now RDS, so there are two *application*
> hosts instead: the home VM and the AWS standby, which need the **same** secret
> set — that is what "pre-configured standby" has to mean, or a failover stops to
> ask for credentials. The agent mechanics below are unchanged; read `vm-wishly`
> as "either application host" and ignore the `vm-db` half.

This replaces hand-maintained `infra/.env` files. Step 1 of
[production-deploy.md](production-deploy.md) still describes the `.env` flow; it is
superseded once this is in place.

---

## 1. The shape

```
   Infisical Cloud  (project: wishly, env: prod)
          │
          │  Universal Auth (client id + secret)
          ▼
   infisical-agent            systemd unit, one per VM
          │  renders a Go template, polls for changes
          ▼
   /opt/wishly/infra/.env     mode 0640, root:docker
          │
          │  execute.command on every re-render
          ▼
   docker compose up -d       picks up the new values
```

**The agent writes to disk and keeps what it wrote.** That is the whole reason to
prefer it over `infisical run -- docker compose up`, which fetches at invocation:
a reboot during an Infisical Cloud outage still brings the stack up from the
cached file. Fetch-at-start would make Infisical a hard dependency of every
restart — including the 2am ones you do because something *else* broke.

**It runs as a systemd unit, not a container.** It has to produce `.env` *before*
Docker Compose reads it, and systemd `Before=` states that dependency natively.
A container that writes a host file another container needs is a startup cycle
with no clean expression.

---

## 2. One machine identity per VM

Least privilege, and it means a compromised app VM cannot read the database
host's credentials.

| Identity | Reads | Used by |
|---|---|---|
| `wishly-vm` | `DATABASE_URL`, `CLERK_*`, `RESEND_*`, `PREFECT_*`, `TUNNEL_TOKEN`, `ALERT_EMAIL_TO` | the PVE VM |
| `wishly-standby` | the same set | the AWS standby EC2 |
| `wishly-backup` | `DATABASE_URL`, `S3_*`, `AWS_*`, `BACKUP_KEEP_LAST` | wherever `compose.backup.yaml` runs |

There is no longer a database-host identity: Postgres is RDS, so `POSTGRES_*`
exists only for the development container in `compose.local.yaml` and never
leaves a workstation. The standby needs the **same** set as the VM — that is what
"pre-configured" has to mean, or a failover stops to ask for credentials.

In the Infisical dashboard:

1. **Access Control → Machine Identities → Create**, auth method **Universal Auth**.
2. Set the token TTL and max TTL. The agent refreshes on its own, so a short
   access-token TTL (e.g. 1h) with a long client-secret lifetime is right.
3. Add the identity to the **wishly** project with **read-only** access to the
   `prod` environment, scoped by secret path or tag to only the rows in its row
   of the table above.
4. Note the **Client ID** and generate a **Client Secret**.

---

## 3. Bootstrap credentials on the host

This is the one secret that lives on disk in plaintext. It is unavoidable —
something has to authenticate first — and it is a single, individually
revocable credential instead of the fifteen currently sitting in `.env`.

```bash
sudo install -d -m 0700 -o root -g root /etc/infisical

printf '%s' '<client-id>'     | sudo tee /etc/infisical/client-id     >/dev/null
printf '%s' '<client-secret>' | sudo tee /etc/infisical/client-secret >/dev/null

sudo chmod 0600 /etc/infisical/client-id /etc/infisical/client-secret
```

`printf` rather than `echo` so no trailing newline ends up in the credential.

If a host is ever compromised, revoke that identity's client secret in the
dashboard — the other VM keeps working.

---

## 4. Install the agent

```bash
# Infisical's apt repo (see their install docs for the current one-liner)
curl -1sLf 'https://artifacts-cli.infisical.com/setup.deb.sh' | sudo -E bash
sudo apt-get update && sudo apt-get install -y infisical

infisical --version
```

---

## 5. Agent configuration

`/etc/infisical/agent.yaml` on **vm-wishly**:

```yaml
infisical:
  address: "https://app.infisical.com"

auth:
  type: "universal-auth"
  config:
    client-id: "/etc/infisical/client-id"
    client-secret: "/etc/infisical/wishly-client-secret"
    remove_client_secret_on_read: false

sinks:
  - type: "file"
    config:
      path: "/etc/infisical/wishly-agent-token"

templates:
  - source-path: /opt/wishly/infra/infisical/env.vm.tmpl
    destination-path: /opt/wishly/infra/.env
    config:
      polling-interval: 60s
      execute:
        command: "/opt/wishly/infra/infisical/reload.sh"
```

> **Check the field names against Infisical's current agent docs before you commit
> this.** The *shape* — auth block, sinks, templates with a poll interval and a
> post-render command — has been stable, but the exact keys have moved across
> releases. Everything else in this runbook is version-independent.

`remove_client_secret_on_read: false` matters: with it true the agent deletes the
client secret after first use, which is a nice hardening property right up until
the VM reboots and cannot re-authenticate.

`infra/infisical/env.vm.tmpl` (in the repo, not `/etc`):

```
{{- with secret "wishly" "prod" "/" }}
{{- range . }}
{{ .Key }}={{ .Value }}
{{- end }}
{{- end }}
```

That renders every secret the identity can see as `KEY=value`. Because access is
scoped per identity (§2), each VM's file contains only its own secrets — the
template does not need to enumerate them, and adding a secret in the dashboard
propagates without a host change.

---

## 5b. macOS workstation — one-shot, no daemon

Everything above targets the Linux VMs. A Mac has no systemd, and a laptop that
sleeps and travels is the wrong place for a long-running agent holding a live
credential. The workstation path renders once, on demand, immediately before the
containers need the values:

```bash
./infra/infisical/up.sh            # render infra/.env, then docker compose up -d
./infra/infisical/up.sh --render   # render only
```

`infra/infisical/agent.mac.yaml` sets `exit-after-auth: true`, so the agent
authenticates, renders, and exits — nothing is left running.

It renders `env.mac.tmpl`, **not** the VM's `env.vm.tmpl`. The two are separate
files on purpose: the Mac runs a Postgres container and the VM uses RDS, so their
`DATABASE_URL` genuinely differs. An earlier revision shared one template and
claimed the two could not drift; that was true only while both hosts ran the same
database, and is now the wrong shape.

**What this gives up:** nothing re-renders on its own. A rotated secret reaches
the Mac on the next `up.sh`, not within a poll interval. Re-run it after any
change in the dashboard.

Machine-identity credentials live outside the repo, in `~/.infisical`:

```bash
printf '%s' '<client-id>'     > ~/.infisical/wishly-client-id
printf '%s' '<client-secret>' > ~/.infisical/wishly-client-secret
chmod 0600 ~/.infisical/wishly-client-id ~/.infisical/wishly-client-secret
```

`printf`, not `echo` — a trailing newline is sent as part of the credential and
authentication fails with a message that does not mention whitespace.

The committed config stores those paths as `__HOME__/...`; `up.sh` substitutes
`$HOME` into a temp copy at run time so no absolute user path is checked in.

## 6. systemd unit

`/etc/systemd/system/infisical-agent.service`:

```ini
[Unit]
Description=Infisical agent — renders /opt/wishly/infra/.env
After=network-online.target
Wants=network-online.target
Before=wishly.service

[Service]
Type=simple
ExecStart=/usr/bin/infisical agent --config /etc/infisical/agent.yaml
Restart=always
RestartSec=10s
User=root

[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/wishly.service`:

```ini
[Unit]
Description=Wishly compose stack
Requires=docker.service infisical-agent.service
After=docker.service infisical-agent.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/wishly/infra/vm-wishly
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now infisical-agent.service wishly.service
```

`Before=`/`After=` order the *start*, but they do not wait for the file to
actually exist. Guard against the first-boot race by having `wishly.service`
refuse to start without it:

```ini
ExecStartPre=/usr/bin/test -s /opt/wishly/infra/.env
```

Failing loudly here is right — the alternative is Compose starting with an empty
env and the API coming up with no `CLERK_FRONTEND_API`, which 401s every request
while looking healthy.

---

## 6a. The agent watches secrets, not the template

**Editing the template does not trigger a re-render.** The agent polls Infisical for
*secret value* changes; the template file itself is read at startup. Change
`env.vm.tmpl` — add a literal, fix an origin — and the agent will happily keep
serving the old render until it restarts.

This is easy to lose an hour to, because everything looks healthy: the agent is
running, the last render succeeded, and the file on disk is simply stale.

```bash
sudo systemctl restart infisical-agent   # after ANY template edit
```

Rotating a secret in the dashboard *does* propagate on its own. Only template
edits need the restart.

## 7. File permissions

```bash
sudo install -d -m 0755 -o root -g root /opt/wishly/infra
sudo touch /opt/wishly/infra/.env
sudo chown root:docker /opt/wishly/infra/.env
sudo chmod 0640 /opt/wishly/infra/.env
```

`0640 root:docker` — Compose reads it as the invoking user, and nothing outside
the `docker` group can read production secrets. Confirm `.env` is git-ignored;
`/opt/wishly` should be a deploy checkout, and this file must never travel back.

---

## 8. vm-db differences

Same install and unit structure, with:

- identity `wishly-vm-db`, so the rendered `.env` holds only `POSTGRES_*`,
  `S3_*`, `AWS_*`, `BACKUP_KEEP_LAST`;
- `destination-path: /opt/wishly/infra/.env` and the `execute.command` pointing
  at `infra/vm-db/docker-compose.yml`;
- the dependent unit named `wishly-db.service`.

A rotated `POSTGRES_PASSWORD` restarts the database container. Rotate it during a
window, and remember `DATABASE_URL` on `vm-wishly` carries the same password —
update both in Infisical together or the app VM will fail auth on next render.

---

## 9. Verify

Three checks. The third is the one people skip and the only one that proves the
design's main claim.

**Rotation propagates.**
```bash
# change a non-critical value in the dashboard, then within the poll interval:
sudo grep ALERT_EMAIL_TO /opt/wishly/infra/.env
docker compose -f /opt/wishly/infra/vm-wishly/docker-compose.yml ps
```

**Permissions hold.**
```bash
sudo -u nobody cat /opt/wishly/infra/.env   # must fail
```

**A reboot survives an Infisical outage.**
```bash
sudo iptables -A OUTPUT -d app.infisical.com -j REJECT   # simulate the outage
sudo reboot
# after boot: the stack is up, from the cached .env
curl -sf localhost:8000/health
sudo iptables -D OUTPUT -d app.infisical.com -j REJECT
```

If that last one fails, something is fetching at startup instead of reading the
rendered file, and the outage-resilience property does not hold.

---

## 10. Rotating

| Secret | How |
|---|---|
| Any app secret | Change in the dashboard; the agent re-renders and re-ups within the poll interval. |
| `POSTGRES_PASSWORD` | Change in the dashboard **and** in `DATABASE_URL` together; both VMs re-render. Do it in a window. |
| Machine identity client secret | Generate a new one in the dashboard, write it to `/etc/infisical/client-secret`, `systemctl restart infisical-agent`, then revoke the old one. |
| `TUNNEL_TOKEN` | Rotate in Cloudflare, update in Infisical; the `cloudflared` container restarts and reconnects. |

---

## 11. Cleaning up the old path

Once both VMs render from the agent (T7 of the plan):

- delete any hand-copied `infra/.env` from the hosts;
- update [production-deploy.md](production-deploy.md) step 1, which still says
  `.env` is the only place production secrets exist;
- `infra/infisical/` in the repo is a merged experiment — `get_secrets.py`,
  `aws_test.py`, `local_file.txt`, and practice scripts hardcoded to a
  `wishly-scratch` bucket and a `pg-backup-practice` container. Promote what this
  runbook actually uses and delete the rest;
- decide whether `infra/infisical/docs-mintlify/` moves here or is dropped. Two
  copies of the same documentation is one too many.
