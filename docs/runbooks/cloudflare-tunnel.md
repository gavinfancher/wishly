# T7.3 — Cloudflare Tunnel Runbook

Create a Cloudflare Tunnel, run `cloudflared` as a Docker Compose service, and route
`api.wishly.dev` to the FastAPI container at `http://api:8000`.

---

## Architecture recap

```
Browser / Clerk webhook / Resend webhook
          │ HTTPS
          ▼
  Cloudflare edge (api.wishly.dev)
          │ encrypted tunnel
          ▼
  cloudflared container (Docker Compose: "cloudflared" service)
          │ HTTP (internal Docker network)
          ▼
  api:8000 (FastAPI / uvicorn container)
```

The tunnel means the Docker host never exposes a public port — all inbound traffic arrives
through Cloudflare's infrastructure.

---

## Prerequisites

- `wishly.dev` is an active zone in your Cloudflare account (same account you will create the
  tunnel in)
- Zero Trust is enabled on the account (it is enabled by default on all accounts — navigate to
  dash.cloudflare.com and click **Zero Trust** in the left sidebar to confirm)
- Docker + Docker Compose are running on the target host
- `infra/compose.yaml` exists with at least the `api` service on a shared network (T7.2)

---

## Step 1 — Create the tunnel in the Cloudflare dashboard

1. Go to **dash.cloudflare.com → Zero Trust → Networks → Connectors → Cloudflare Tunnels**
2. Click **Create a tunnel**
3. Select **Cloudflared** as the connector type, click **Next**
4. Name the tunnel: `wishly-prod`
5. Click **Save tunnel**

On the next screen, select **Docker** as the environment. The dashboard displays an installation
command that looks like:

```
docker run cloudflare/cloudflared:latest tunnel --no-autoupdate run --token eyJhIjoi...
```

**Copy the token string** (the `eyJ...` value). This is your `TUNNEL_TOKEN`. Store it
immediately — do not run the command from here.

---

## Step 2 — Configure the public hostname

Immediately after saving the tunnel, the dashboard prompts you to add a **Public Hostname**.
Fill in:

| Field | Value |
|---|---|
| Subdomain | `api` |
| Domain | `wishly.dev` (selected from dropdown) |
| Service Type | `HTTP` |
| URL | `http://api:8000` |

Click **Save tunnel**.

Cloudflare automatically creates the following CNAME record in the `wishly.dev` DNS zone:

```
api.wishly.dev  CNAME  <tunnel-uuid>.cfargotunnel.com  (Proxied)
```

Verify this appeared in **dash.cloudflare.com → wishly.dev → DNS → Records**. The proxy status
must be **Proxied** (orange cloud) — do not change it to DNS Only.

> **If you skipped the hostname step**, you can add it later via
> **Zero Trust → Tunnels → wishly-prod → Edit → Public Hostnames → Add a public hostname**.
> The DNS CNAME record is created automatically when you save.

---

## Step 3 — Store the tunnel token

Add the token to `infra/.env` (never commit this file):

```
TUNNEL_TOKEN=eyJhIjoiNW...
```

This is the only credential `cloudflared` needs. It encodes the account ID, tunnel ID, and
tunnel secret.

---

## Step 4 — Add the cloudflared service to Docker Compose

In `infra/compose.yaml`, add the `cloudflared` service alongside `api`:

```yaml
services:
  api:
    build:
      context: ..
      dockerfile: infra/Dockerfile.api
    restart: unless-stopped
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - CLERK_SECRET_KEY=${CLERK_SECRET_KEY}
      - CLERK_WEBHOOK_SIGNING_SECRET=${CLERK_WEBHOOK_SIGNING_SECRET}
      - RESEND_API_KEY=${RESEND_API_KEY}
      - RESEND_WEBHOOK_SIGNING_SECRET=${RESEND_WEBHOOK_SIGNING_SECRET}
      - EMAIL_FROM=${EMAIL_FROM}
      - APP_BASE_URL=${APP_BASE_URL}
      - ALLOWED_ORIGINS=${ALLOWED_ORIGINS}
      - ENVIRONMENT=${ENVIRONMENT}
    networks:
      - app_net
    # No ports: published to the host — cloudflared reaches api via the internal network

  cloudflared:
    image: cloudflare/cloudflared:latest
    restart: unless-stopped
    command: tunnel --no-autoupdate run
    environment:
      - TUNNEL_TOKEN=${TUNNEL_TOKEN}
    networks:
      - app_net
    depends_on:
      - api

networks:
  app_net:
    driver: bridge
```

Key points:

- The `api` service does **not** need `ports: ["8000:8000"]`. Publishing ports to the host is
  unnecessary and increases attack surface. `cloudflared` reaches `api:8000` over the shared
  `app_net` Docker network using Docker's internal DNS.
- `--no-autoupdate` disables in-container self-updates; upgrades happen by pulling a new image tag.
- `TUNNEL_TOKEN` is the only env var `cloudflared` requires for a remotely-managed tunnel.

---

## Step 5 — Start (or restart) the stack

```bash
docker compose -f infra/compose.yaml --env-file infra/.env up -d
```

Watch `cloudflared` logs to confirm the tunnel connects:

```bash
docker compose -f infra/compose.yaml logs cloudflared -f
```

A healthy startup produces lines like:

```
Registered tunnel connection connIndex=0 connection=<uuid> location=<datacenter>
Registered tunnel connection connIndex=1 ...
```

`cloudflared` opens four connections to at least two Cloudflare data centres. If you see
`failed to connect` or `context deadline exceeded`, verify outbound port 443 is not blocked on
the host.

---

## Step 6 — Verify the tunnel is healthy

### 6a. Dashboard status

**Zero Trust → Networks → Connectors → Cloudflare Tunnels → wishly-prod**

Status should read **Healthy** (green). If it reads **Inactive**, the container has not yet
connected; **Down** means no connector has been running; **Degraded** means only some connections
are up.

### 6b. End-to-end health check from the public internet

```bash
curl -i https://api.wishly.dev/health
```

Expected:

```
HTTP/2 200
content-type: application/json

{"status": "ok"}
```

This confirms the full path: DNS → Cloudflare edge → tunnel → `cloudflared` → `api:8000` → FastAPI
`/health` route.

### 6c. Test from a remote machine or browser

Visit `https://api.wishly.dev/health` in a browser on a different network than the Docker host.
A 200 response with JSON body confirms the tunnel is live.

---

## Step 7 — Optional: enable metrics for healthchecks

For Docker healthcheck or Prometheus scraping, add `--metrics 0.0.0.0:2000` to the command:

```yaml
  cloudflared:
    image: cloudflare/cloudflared:latest
    restart: unless-stopped
    command: tunnel --no-autoupdate --metrics 0.0.0.0:2000 run
    environment:
      - TUNNEL_TOKEN=${TUNNEL_TOKEN}
    networks:
      - app_net
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:2000/ready"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
```

`GET http://localhost:2000/ready` returns HTTP 200 only when the tunnel has an active connection
to Cloudflare.

---

## Updating the cloudflared image

`cloudflare/cloudflared:latest` tracks the latest release. To pin a specific version (recommended
for production):

```yaml
    image: cloudflare/cloudflared:2025.4.0
```

Check current releases at hub.docker.com/r/cloudflare/cloudflared/tags.

To update:

```bash
docker compose -f infra/compose.yaml pull cloudflared
docker compose -f infra/compose.yaml up -d cloudflared
```

---

## Rotating the tunnel token

1. **Zero Trust → Tunnels → wishly-prod → Edit → Overview → Refresh token**
2. Copy the new token
3. Update `TUNNEL_TOKEN` in `infra/.env`
4. Restart the container: `docker compose -f infra/compose.yaml up -d cloudflared`

If you have multiple `cloudflared` replicas (e.g. on two hosts), update each `.env` and restart
one at a time to avoid downtime.

---

## Ingress config reference (locally-managed equivalent)

The remotely-managed tunnel stores ingress rules in Cloudflare's API. If you ever need to switch
to a file-based locally-managed tunnel (e.g. for offline dev), the equivalent
`infra/cloudflared/config.yml` is:

```yaml
tunnel: <tunnel-uuid>
credentials-file: /etc/cloudflared/creds.json

ingress:
  - hostname: api.wishly.dev
    service: http://api:8000
  - service: http_status:404   # required catch-all
```

The `TUNNEL_TOKEN` approach (remotely-managed) is preferred for production — no credentials file
needed and ingress rules can be updated from the dashboard without restarting connectors.

---

## QUESTIONS

None — the tunnel approach (remotely-managed, dashboard public hostname, Docker Compose service)
is fully specified in PLAN §2 and §3.
