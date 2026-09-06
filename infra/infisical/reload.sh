#!/usr/bin/env bash
# Post-render hook for the Infisical agent on the PVE VM.
#
# The agent runs this after every render of /opt/wishly/infra/.env (see the
# `execute.command` in agent.vm.yaml). Its job is to validate what was written
# and only then let Docker Compose pick it up.
#
# Why validate at all: the rendered file is whatever the machine identity can
# READ, plus the literals in env.vm.tmpl. If a secret is missing from Infisical
# or the identity is not scoped to it, the key simply vanishes — no error. The
# stack then comes up looking healthy while cloudflared has no tunnel or the API
# has no Clerk key.
#
# On a bad render this refuses to run compose and exits non-zero. That is
# deliberate: the containers keep running with the configuration they were
# created with, because Compose only reads .env at `up`. A broken render should
# cost you an alert, not the running stack.
set -euo pipefail

REPO_ROOT="${WISHLY_ROOT:-/opt/wishly}"
ENV_FILE="$REPO_ROOT/infra/.env"

log() { echo "[wishly-reload] $*"; }

if [[ ! -s "$ENV_FILE" ]]; then
  log "error: $ENV_FILE is missing or empty; not touching the stack" >&2
  exit 1
fi

# Every key the stack needs to come up correctly. Keep in sync with
# infra/.env.example. POSTGRES_* are absent on purpose: this host talks to
# PlanetScale, and the only Postgres container lives in the local overlay, which
# is not used here.
REQUIRED=(
  DATABASE_URL
  TUNNEL_TOKEN RESEND_API_KEY EMAIL_FROM
  CLERK_SECRET_KEY CLERK_FRONTEND_API
  PREFECT_API_URL PREFECT_API_KEY
  ALLOWED_ORIGINS APP_BASE_URL ENVIRONMENT AUTH_DEV_BYPASS
)
MISSING=()
for k in "${REQUIRED[@]}"; do
  grep -qE "^${k}=." "$ENV_FILE" || MISSING+=("$k")
done
if (( ${#MISSING[@]} )); then
  log "error: rendered $ENV_FILE is missing required keys:" >&2
  printf '  %s\n' "${MISSING[@]}" >&2
  log "Add them to Infisical or widen the identity's scope. Stack left as-is." >&2
  exit 1
fi

# PlanetScale refuses a plaintext connection. Catching it here turns a confusing
# runtime failure into a named one.
if ! grep -qE '^DATABASE_URL=.*sslmode=' "$ENV_FILE"; then
  log "error: DATABASE_URL has no sslmode= parameter." >&2
  log "The database refuses non-TLS connections; add ?sslmode=require to the DSN." >&2
  exit 1
fi

chmod 0640 "$ENV_FILE"

# Never print values — only which keys arrived.
log "$ENV_FILE validated; keys: $(grep -oE '^[A-Z_]+=' "$ENV_FILE" | tr -d '=' | sort | tr '\n' ' ')"

cd "$REPO_ROOT"

# No compose.local.yaml: that overlay exists to add a Postgres container, and
# this host talks to PlanetScale. Adding it here would start a second, empty
# database and quietly point the app at it.
log "docker compose up -d"
docker compose -f infra/compose.yaml --env-file infra/.env up -d

log "done"
