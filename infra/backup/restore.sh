#!/usr/bin/env sh
# Restore a Postgres dump produced by backup.sh (PLAN T8.3).
#
# Usage:
#   DATABASE_URL=postgresql://user:pass@host:5432/db restore.sh /backups/wishly_<ts>.dump
#
# --clean --if-exists drops existing objects before recreating them, so the
# target database must already exist (create it empty first for a fresh restore).
set -eu

if [ "$#" -ne 1 ]; then
  echo "usage: restore.sh <dumpfile>" >&2
  exit 2
fi
dumpfile="$1"

if [ -z "${DATABASE_URL:-}" ]; then
  echo "restore: DATABASE_URL is required" >&2
  exit 1
fi
if [ ! -f "$dumpfile" ]; then
  echo "restore: no such dump file: $dumpfile" >&2
  exit 1
fi

echo "restore: restoring $dumpfile into target database"
pg_restore --clean --if-exists --no-owner --no-acl --dbname="$DATABASE_URL" "$dumpfile"
echo "restore: done"
