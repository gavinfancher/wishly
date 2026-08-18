#!/usr/bin/env sh
# Postgres backup (PLAN T8.3). Dumps the database, uploads the dump to S3, then
# prunes old local copies.
#
# A dump that stays on the same host as the database is not a backup — the box
# dying takes both. S3_BUCKET is therefore required unless BACKUP_S3_OPTIONAL=1
# (local-only, for development).
#
# Config via env:
#   DATABASE_URL          full DSN, e.g. postgresql://wishly:wishly@postgres:5432/wishly
#   S3_BUCKET             destination bucket, e.g. wishly-backups
#   S3_PREFIX             key prefix within the bucket (default wishly/postgres)
#   S3_ENDPOINT_URL       set for S3-compatible stores (Cloudflare R2, MinIO);
#                         leave unset for AWS S3
#   AWS_ACCESS_KEY_ID     credentials for the above
#   AWS_SECRET_ACCESS_KEY
#   AWS_DEFAULT_REGION    default us-east-1 (R2 accepts "auto")
#   BACKUP_DIR            local staging directory (default /backups)
#   RETENTION_DAYS        delete local dumps older than this (default 14).
#                         Remote retention belongs to a bucket lifecycle rule —
#                         see docs/runbooks/backup-restore.md.
#   BACKUP_S3_OPTIONAL    "1" to skip the upload instead of failing
#
# Custom format (-Fc) is restored with pg_restore (see restore.sh) and supports
# selective/parallel restore.
set -eu

BACKUP_DIR="${BACKUP_DIR:-/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
S3_PREFIX="${S3_PREFIX:-wishly/postgres}"
AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"
export AWS_DEFAULT_REGION

if [ -z "${DATABASE_URL:-}" ]; then
  echo "backup: DATABASE_URL is required" >&2
  exit 1
fi

if [ -z "${S3_BUCKET:-}" ] && [ "${BACKUP_S3_OPTIONAL:-0}" != "1" ]; then
  echo "backup: S3_BUCKET is required (set BACKUP_S3_OPTIONAL=1 to keep dumps local only)" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
outfile="$BACKUP_DIR/wishly_${timestamp}.dump"

echo "backup: dumping to $outfile"
pg_dump --format=custom --no-owner --no-acl --dbname="$DATABASE_URL" --file="$outfile"

if [ -n "${S3_BUCKET:-}" ]; then
  # Partition by day so a bucket listing stays navigable at hourly cadence.
  day="$(echo "$timestamp" | cut -c1-8)"
  key="s3://${S3_BUCKET}/${S3_PREFIX}/${day}/wishly_${timestamp}.dump"

  # Only pass --endpoint-url when set, so AWS S3 uses its default resolution.
  if [ -n "${S3_ENDPOINT_URL:-}" ]; then
    aws s3 cp "$outfile" "$key" --endpoint-url "$S3_ENDPOINT_URL" --only-show-errors
  else
    aws s3 cp "$outfile" "$key" --only-show-errors
  fi
  echo "backup: uploaded $key"
else
  echo "backup: S3_BUCKET unset — keeping local copy only"
fi

echo "backup: pruning local dumps older than ${RETENTION_DAYS} day(s)"
find "$BACKUP_DIR" -name 'wishly_*.dump' -type f -mtime "+${RETENTION_DAYS}" -print -delete

echo "backup: done ($(ls -1 "$BACKUP_DIR"/wishly_*.dump 2>/dev/null | wc -l | tr -d ' ') local dump(s) retained)"
