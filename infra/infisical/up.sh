#!/usr/bin/env bash
# Render infra/.env from Infisical, then bring the local stack up.
#
#   ./infra/infisical/up.sh            # render + up -d
#   ./infra/infisical/up.sh --render   # render only, don't touch containers
#
# macOS workstation equivalent of the systemd agent in docs/runbooks/secrets.md.
# One-shot: no daemon is left running. Re-run it whenever a secret changes.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

CRED_DIR="${INFISICAL_CRED_DIR:-$HOME/.infisical}"
ENV_FILE="infra/.env"

for f in wishly-client-id wishly-client-secret; do
  if [[ ! -s "$CRED_DIR/$f" ]]; then
    echo "error: missing $CRED_DIR/$f" >&2
    echo "  Write the machine identity credentials with printf (NOT echo — a" >&2
    echo "  trailing newline is sent as part of the credential and auth fails):" >&2
    echo "    printf '%s' '<client-id>'     > $CRED_DIR/wishly-client-id" >&2
    echo "    printf '%s' '<client-secret>' > $CRED_DIR/wishly-client-secret" >&2
    echo "    chmod 0600 $CRED_DIR/wishly-*" >&2
    exit 1
  fi
done

# The committed config carries __HOME__ so no absolute user path is checked in.
# Rendered to a private temp file; the agent never reads the repo copy directly.
RENDERED_CFG="$(mktemp -t wishly-infisical-agent)"
trap 'rm -f "$RENDERED_CFG"' EXIT
sed "s|__HOME__|$HOME|g" infra/infisical/agent.mac.yaml > "$RENDERED_CFG"

# Keep the previous file: if the agent fails partway we restore rather than
# leaving compose pointed at a truncated .env.
BACKUP=""
if [[ -f "$ENV_FILE" ]]; then
  BACKUP="$(mktemp -t wishly-env-backup)"
  cp "$ENV_FILE" "$BACKUP"
fi

echo "==> rendering $ENV_FILE from Infisical (one-shot)"
if ! infisical agent --config "$RENDERED_CFG"; then
  echo "error: agent failed" >&2
  if [[ -n "$BACKUP" ]]; then
    cp "$BACKUP" "$ENV_FILE"
    echo "restored previous $ENV_FILE" >&2
  fi
  rm -f "${BACKUP:-}"
  exit 1
fi

# The rendered file is whatever the identity can READ plus the literals in
# env.mac.tmpl. If a secret is missing from Infisical dev — or the identity is not
# scoped to it — the key simply vanishes, and the stack comes up looking healthy
# while cloudflared has no tunnel or the API has no Clerk key. Fail loudly and
# put the working file back instead.
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
  echo "error: rendered $ENV_FILE is missing required keys:" >&2
  printf '  %s\n' "${MISSING[@]}" >&2
  echo "Add them to Infisical (env dev) or widen the machine" >&2
  echo "identity's scope, then re-run. Not starting the stack." >&2
  if [[ -n "$BACKUP" ]]; then
    cp "$BACKUP" "$ENV_FILE"
    echo "restored previous $ENV_FILE" >&2
  fi
  rm -f "${BACKUP:-}"
  exit 1
fi

rm -f "${BACKUP:-}"

chmod 0600 "$ENV_FILE"

# Never print values — only which keys arrived.
echo "==> $ENV_FILE rendered; keys:"
grep -oE '^[A-Z_]+=' "$ENV_FILE" | tr -d '=' | sort | tr '\n' ' '
echo

if [[ "${1:-}" == "--render" ]]; then
  echo "==> --render given; leaving containers alone"
  exit 0
fi

echo "==> docker compose up -d"
# Both -f flags are required: compose.local.yaml is an overlay, not a stack.
docker compose -f infra/compose.yaml -f infra/compose.local.yaml \
  --env-file "$ENV_FILE" up -d

echo "==> waiting for health"
for i in $(seq 1 30); do
  if curl -fsS -m 3 localhost:8000/ready >/dev/null 2>&1; then
    echo "api ready: $(curl -fsS -m 3 localhost:8000/ready)"
    exit 0
  fi
  sleep 2
done
echo "warning: api did not report ready within 60s — check: docker compose logs api" >&2
exit 1
