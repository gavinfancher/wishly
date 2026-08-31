#!/usr/bin/env bash
# Rebuild and roll the Wishly containers on the application host.
#
#   ./infra/deploy.sh                      # run on the VM itself
#   ./infra/deploy.sh --host wishly-vm     # run from your laptop, over ssh
#   ./infra/deploy.sh --rollback           # put the previous images back
#
# WHY THIS EXISTS. The frontend deploys itself: Cloudflare builds on push to
# main. The backend does not. It is a container image built on the host, so a
# backend fix pushed to main is *not live* until something rebuilds it — and the
# gap is invisible, because the old container keeps answering health checks
# perfectly while serving the old code.
#
# Not to be confused with infra/infisical/reload.sh, which the agent runs when a
# *secret* changes: that only re-runs `up -d` to pick up new environment values
# and never rebuilds. Config changed -> reload.sh. Code changed -> this.
#
# The frontend is untouched here.
set -euo pipefail

REPO="${WISHLY_ROOT:-/opt/wishly}"
COMPOSE=(docker compose -f infra/compose.yaml --env-file infra/.env)
# Only these are built from source. `schema` uses the stock postgres image and
# `cloudflared` Cloudflare's, so rebuilding them would be a no-op at best.
SERVICES=(api worker)
HEALTH_TIMEOUT=120

REMOTE_HOST=""
ROLLBACK=false
SKIP_PULL=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) REMOTE_HOST="${2:-}"; shift 2 ;;
    --rollback) ROLLBACK=true; shift ;;
    --no-pull) SKIP_PULL=true; shift ;;
    -h|--help) sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

# --- Remote mode -------------------------------------------------------------
# Pull first, then run the *pulled* copy of this script, so a fix to the deploy
# process itself takes effect on the deploy that ships it.
if [[ -n "$REMOTE_HOST" ]]; then
  args=()
  $ROLLBACK && args+=(--rollback)
  $SKIP_PULL && args+=(--no-pull)
  exec ssh -t "$REMOTE_HOST" \
    "cd '$REPO' && { [ '$SKIP_PULL' = true ] || git pull -q --ff-only; } && ./infra/deploy.sh ${args[*]:-}"
fi

cd "$REPO"
log() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
die() { printf '\033[31merror: %s\033[0m\n' "$*" >&2; exit 1; }

[[ -f infra/compose.yaml ]] || die "no infra/compose.yaml under $REPO — wrong host, or set WISHLY_ROOT"
[[ -s infra/.env ]] || die "infra/.env is missing or empty; the Infisical agent should render it"

# --- Rollback ----------------------------------------------------------------
if $ROLLBACK; then
  log "Rolling back to the previous images"
  for svc in "${SERVICES[@]}"; do
    img="wishly-${svc}"
    sudo docker image inspect "${img}:previous" >/dev/null 2>&1 \
      || die "no ${img}:previous to roll back to (has this host ever deployed?)"
    sudo docker tag "${img}:previous" "${img}:latest"
    echo "  ${img}:previous -> ${img}:latest"
  done
  sudo "${COMPOSE[@]}" up -d "${SERVICES[@]}"
  log "Rolled back. The working tree still points at $(git rev-parse --short HEAD) — reset it if the code was the problem."
  exit 0
fi

# --- Guard the working tree --------------------------------------------------
# A dirty tree means someone edited on the host. Pulling over it either fails or
# silently merges; either way it is not what this script should decide.
if [[ -n "$(git status --porcelain)" ]]; then
  git status --short | sed 's/^/    /'
  die "working tree is dirty on the host — commit, stash, or discard before deploying"
fi

BEFORE="$(git rev-parse --short HEAD)"

if ! $SKIP_PULL; then
  log "Fetching"
  # --ff-only: refuse to invent a merge commit on a deploy host.
  git pull -q --ff-only || die "cannot fast-forward — the host has diverged from origin"
fi

AFTER="$(git rev-parse --short HEAD)"
if [[ "$BEFORE" == "$AFTER" ]]; then
  echo "  already at $AFTER; rebuilding anyway so a local image drift cannot persist"
else
  log "Changes coming in ($BEFORE -> $AFTER)"
  git --no-pager log --oneline "$BEFORE..$AFTER" | sed 's/^/    /'
fi

# --- Keep a way back ---------------------------------------------------------
# Tag what is running before replacing it. Without this a bad deploy has no
# route back except rebuilding an older commit, which takes minutes you do not
# want to spend while the API is down.
log "Tagging the running images as :previous"
for svc in "${SERVICES[@]}"; do
  img="wishly-${svc}"
  if sudo docker image inspect "${img}:latest" >/dev/null 2>&1; then
    sudo docker tag "${img}:latest" "${img}:previous"
    echo "  ${img}:latest -> ${img}:previous"
  else
    echo "  ${img}:latest does not exist yet (first deploy)"
  fi
done

# --- Build and roll ----------------------------------------------------------
# Worth knowing: restarting the worker kills an in-flight send. That cannot cause
# a duplicate — notification_log's unique constraint sees to that — but a run
# interrupted mid-send can leave its row `pending` rather than `sent`. Deploying
# away from the top of the hour avoids the question entirely.
log "Building ${SERVICES[*]}"
sudo "${COMPOSE[@]}" build "${SERVICES[@]}"

log "Recreating containers"
# `schema` is included so schema.sql is applied before the API starts against a
# database that may be missing a table the new code expects. It is idempotent.
sudo "${COMPOSE[@]}" up -d schema "${SERVICES[@]}"

# --- Verify ------------------------------------------------------------------
log "Waiting for the API to report ready (up to ${HEALTH_TIMEOUT}s)"
deadline=$(( SECONDS + HEALTH_TIMEOUT ))
ready=false
while (( SECONDS < deadline )); do
  if sudo "${COMPOSE[@]}" exec -T api python -c "
import sys, urllib.request
try:
    sys.exit(0 if urllib.request.urlopen('http://localhost:8000/ready', timeout=3).status == 200 else 1)
except Exception:
    sys.exit(1)
" >/dev/null 2>&1; then
    ready=true; break
  fi
  sleep 3
done

if ! $ready; then
  printf '\n\033[31m==> API did not become ready\033[0m\n'
  sudo "${COMPOSE[@]}" logs api --tail 30
  printf '\n\033[31mRoll back with:  %s --rollback\033[0m\n' "$0"
  exit 1
fi

# /ready hits Postgres, so this also proves the RDS connection survived.
log "Deployed"
sudo "${COMPOSE[@]}" ps --format '  {{.Service}}  {{.State}}  {{.Status}}'
echo
echo "  commit : $(git log --oneline -1)"
echo "  rollback if needed: $0 --rollback"
