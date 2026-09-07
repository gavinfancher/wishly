#!/usr/bin/env bash
# Build the detector's deployment zip.
#
#   ./infra/lambda/build.sh
#
# Installs dependencies for the LAMBDA's platform, not this laptop's. pendulum
# ships native wheels, so a macOS arm64 wheel would import-error in Lambda with
# a message that says nothing useful about why. --python-platform makes uv
# resolve manylinux aarch64 wheels instead.
#
# boto3 is not bundled: the Lambda runtime already has it, and adding it costs
# ~15 MB of cold-start pull for nothing.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

BUILD=build
rm -rf "$BUILD" detector.zip
mkdir -p "$BUILD"

uv pip install \
  --target "$BUILD" \
  --python-platform aarch64-manylinux2014 \
  --python-version 3.12 \
  --only-binary=:all: \
  --quiet \
  httpx pendulum

cp detector/handler.py "$BUILD/"
(cd "$BUILD" && zip -qr ../detector.zip .)
echo "detector.zip  $(du -h detector.zip | cut -f1)"
