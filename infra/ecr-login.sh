#!/usr/bin/env bash
# Authenticate docker against ECR, using the credentials already in infra/.env.
#
#   ./infra/ecr-login.sh
#
# The token lasts 12 hours, so this is a per-deploy step rather than something
# to schedule. Reading the keys from infra/.env keeps one source of truth: the
# same file the containers get their AWS credentials from, so a rotation is one
# edit rather than two.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

REGION="${AWS_REGION:-us-east-1}"
ENV_FILE="infra/.env"

if [[ -f "$ENV_FILE" ]]; then
  # Only the AWS keys — sourcing the whole file would drag DATABASE_URL and the
  # rest into this shell for no reason.
  eval "$(grep -E '^AWS_(ACCESS_KEY_ID|SECRET_ACCESS_KEY)=' "$ENV_FILE" | sed 's/^/export /')"
fi

ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
REGISTRY="${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"

aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "$REGISTRY"
