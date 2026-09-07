#!/usr/bin/env bash
# Build the Wishly images and push them to ECR, tagged with the commit.
#
#   ./infra/images.sh              # build both, tag with the short SHA
#   ./infra/images.sh --push       # build, then push
#
# The tag is the commit so "which source is this?" needs nobody's memory, and
# ECR has immutable tags so a tag can never come to mean different bytes. That
# is what lets `docker images --digests` and `aws ecr describe-images` be
# compared: same digest, or "the same containers" is just a claim.
#
# amd64 everywhere. The PVE VM is x86_64, so this is the one architecture both
# runtimes can share — and sharing one means the VM and ECS pull the SAME image
# digest rather than running two builds of the same source. Graviton would be
# ~20% cheaper on Fargate (about $0.11/month here), which is not worth giving up
# that guarantee. Building amd64 on an Apple Silicon Mac is emulated but costs
# seconds, because this image installs wheels rather than compiling.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
REGION="${AWS_REGION:-us-east-1}"
PUSH=false
[[ "${1:-}" == "--push" ]] && PUSH=true

TAG="$(git rev-parse --short HEAD)"
if [[ -n "$(git status --porcelain)" ]]; then
  # A tag naming a commit that does not describe the bytes is worse than none.
  $PUSH && { echo "error: working tree is dirty; commit before pushing" >&2; exit 1; }
  TAG="${TAG}-dirty"
fi

for svc in api worker; do
  echo "==> building wishly-$svc:$TAG"
  # --provenance=false: the default attestation makes a manifest list, which
  # some ECS/ECR tooling reports as "image not found" for the platform it wants.
  docker buildx build --platform linux/amd64 --provenance=false \
    -f "infra/Dockerfile.$svc" -t "wishly-$svc:$TAG" --load .
done

$PUSH || { echo "built at $TAG (use --push to publish)"; exit 0; }

# The VM runs this same script to authenticate, so the login lives in one place.
./infra/ecr-login.sh

ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
REGISTRY="${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"

for svc in api worker; do
  docker tag "wishly-$svc:$TAG" "$REGISTRY/wishly-$svc:$TAG"
  docker push "$REGISTRY/wishly-$svc:$TAG"
  aws ecr describe-images --repository-name "wishly-$svc" --image-ids "imageTag=$TAG" \
    --region "$REGION" --query 'imageDetails[0].imageDigest' --output text
done
