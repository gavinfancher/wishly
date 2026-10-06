#!/usr/bin/env bash
# Pull the newest image and (re)start Wishly, with every secret from Infisical.
# Lives at /opt/wishly/deploy.sh on the VM (Ansible puts it there). The GitHub
# Actions deploy job runs it; you can also run it by hand over SSH.
set -euo pipefail
cd "$(dirname "$0")"

# The machine identity Ansible wrote: INFISICAL_CLIENT_ID, INFISICAL_CLIENT_SECRET,
# INFISICAL_PROJECT_ID, INFISICAL_ENV.
source ./infisical.env

# Trade the long-lived identity for a short-lived access token.
INFISICAL_TOKEN=$(infisical login --method=universal-auth \
  --client-id="$INFISICAL_CLIENT_ID" --client-secret="$INFISICAL_CLIENT_SECRET" \
  --silent --plain)
export INFISICAL_TOKEN

with_secrets() {
  infisical run --projectId="$INFISICAL_PROJECT_ID" --env="$INFISICAL_ENV" --silent -- "$@"
}

with_secrets docker compose pull
# --wait: return only once every container passes its healthcheck, and fail
# (so the deploy job fails) if one doesn't.
with_secrets docker compose up -d --wait --remove-orphans
docker image prune -f >/dev/null # drop images no container uses any more
docker compose ps
