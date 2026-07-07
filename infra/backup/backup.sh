#!/usr/bin/env sh
# Postgres backup (PLAN T8.3). Writes a compressed custom-format dump and prunes
# old ones. Designed to run inside a postgres:16 container (has pg_dump) — see
# infra/backup/docker-compose.backup.yml — or on a host with libpq tools.
#
# Config via env:
#   DATABASE_URL    full DSN (preferred), e.g. postgresql://wishly:wishly@postgres:5432/wishly
#   BACKUP_DIR      output directory (default /backups)
#   RETENTION_DAYS  delete dumps older than this (default 14)
#
# Custom format (-Fc) is restored with pg_restore (see restore.sh) and supports
# selective/parallel restore.
set -eu

BACKUP_DIR="${BACKUP_DIR:-/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

if [ -z "${DATABASE_URL:-}" ]; then
  echo "backup: DATABASE_URL is required" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
outfile="$BACKUP_DIR/wishly_${timestamp}.dump"

echo "backup: dumping to $outfile"
pg_dump --format=custom --no-owner --no-acl --dbname="$DATABASE_URL" --file="$outfile"

echo "backup: pruning dumps older than ${RETENTION_DAYS} day(s)"
find "$BACKUP_DIR" -name 'wishly_*.dump' -type f -mtime "+${RETENTION_DAYS}" -print -delete

echo "backup: done ($(ls -1 "$BACKUP_DIR"/wishly_*.dump 2>/dev/null | wc -l | tr -d ' ') dump(s) retained)"
