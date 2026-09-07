#!/usr/bin/env bash
# Roll the VM to an image tag. Runs ON the VM.
#
#   ./infra/deploy-vm.sh <tag>
#
# One code path for a manual deploy, the runbook, and CI, so the thing you
# rehearse is the thing that runs. It pulls first and swaps second, keeping the
# window where the API is down as short as it can be — which matters more here
# than usual, because the detector Lambda fails over to ECS after ~3 minutes of
# a missing host and does not care that you are the one who took it down.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

TAG="${1:-}"
[[ -n "$TAG" ]] || { echo "usage: $0 <image-tag>   (e.g. $(git rev-parse --short HEAD 2>/dev/null || echo 14ce64f))" >&2; exit 1; }

ENV_FILE="infra/.env"
[[ -f "$ENV_FILE" ]] || { echo "error: $ENV_FILE not found — this script runs on the VM" >&2; exit 1; }
compose() { docker compose -f infra/compose.yaml --env-file "$ENV_FILE" "$@"; }

echo "==> authenticating to ECR"
./infra/ecr-login.sh

echo "==> pinning WISHLY_TAG=$TAG"
# -i.bak then remove: the only spelling of in-place sed that works on both GNU
# (the VM) and BSD (a Mac, if this is ever run from one).
sed -i.bak "s|^WISHLY_TAG=.*|WISHLY_TAG=${TAG}|" "$ENV_FILE" && rm -f "${ENV_FILE}.bak"
grep -q "^WISHLY_TAG=${TAG}$" "$ENV_FILE" || { echo "error: failed to set WISHLY_TAG" >&2; exit 1; }

echo "==> pulling (containers still serving)"
compose pull

echo "==> swapping"
compose up -d
# cloudflared runs inside the API's network namespace, so replacing the API
# container orphans it — it keeps running against a namespace that is gone, and
# the tunnel goes quiet without the container ever looking unhealthy.
compose up -d --force-recreate cloudflared

echo "==> waiting for the API to report healthy"
for _ in $(seq 1 45); do
  cid="$(compose ps -q api)"
  [[ -n "$cid" ]] || { sleep 2; continue; }
  state="$(docker inspect --format '{{.State.Health.Status}}' "$cid" 2>/dev/null || echo starting)"
  [[ "$state" == healthy ]] && break
  sleep 2
done
[[ "${state:-}" == healthy ]] || {
  echo "error: API did not become healthy; last state=${state:-unknown}" >&2
  compose logs --tail 40 api >&2
  exit 1
}

# "Same image" is a claim until the digests are compared. Print what is actually
# running so a deploy that silently kept the old container is visible here
# rather than during a failover.
echo "==> running digests"
for svc in api worker; do
  docker inspect --format "{{index .RepoDigests 0}}" \
    "$(compose ps -q "$svc")" 2>/dev/null || echo "  $svc: no digest (locally built?)"
done

echo "==> deployed $TAG"
