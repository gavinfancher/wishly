#!/usr/bin/env bash
# Create (or update) the `wishly` Secret that every pod in the namespace reads.
# It's the one piece of the cluster that isn't in git, because it holds the
# credentials. Safe to re-run: it replaces the Secret with the current values.
#
#   WISHLY_DATABASE_URL=postgresql://wishly_app:<pw>@postgres.ad.gavinf.com:5432/wishly \
#   WISHLY_RESEND_API_KEY=re_... \
#   deploy/create-secret.sh
#
# Optional: WISHLY_SIGNUP_ENABLED=false once everyone has an account.
# The ping key, tunnel token and CORS origin come from Terraform's output, so
# run `terraform apply` in infra/terraform first. Values go straight from this
# shell to the cluster; nothing is written to disk.
set -euo pipefail
cd "$(dirname "$0")/.."

: "${WISHLY_DATABASE_URL:?set WISHLY_DATABASE_URL (the wishly_app role)}"
: "${WISHLY_RESEND_API_KEY:?set WISHLY_RESEND_API_KEY (from Resend)}"

tf=$(terraform -chdir=infra/terraform output -json cluster_secret_values)
from_tf() { jq -r --arg k "$1" '.[$k]' <<<"$tf"; }

args=(
  --from-literal=WISHLY_DATABASE_URL="$WISHLY_DATABASE_URL"
  --from-literal=WISHLY_RESEND_API_KEY="$WISHLY_RESEND_API_KEY"
  --from-literal=WISHLY_PING_TOKEN="$(from_tf WISHLY_PING_TOKEN)"
  --from-literal=WISHLY_CORS_ORIGINS="$(from_tf WISHLY_CORS_ORIGINS)"
  --from-literal=TUNNEL_TOKEN="$(from_tf TUNNEL_TOKEN)"
)
if [[ -n "${WISHLY_SIGNUP_ENABLED:-}" ]]; then
  args+=(--from-literal=WISHLY_SIGNUP_ENABLED="$WISHLY_SIGNUP_ENABLED")
fi

kubectl get namespace wishly >/dev/null 2>&1 || kubectl create namespace wishly
# create --dry-run | apply: creates the Secret the first time, replaces it after.
kubectl -n wishly create secret generic wishly "${args[@]}" --dry-run=client -o yaml |
  kubectl apply -f -

# Pods read env vars only at start, so restart whatever already runs.
for deploy in wishly-api cloudflared; do
  if kubectl -n wishly get deployment "$deploy" >/dev/null 2>&1; then
    kubectl -n wishly rollout restart deployment "$deploy"
  fi
done
