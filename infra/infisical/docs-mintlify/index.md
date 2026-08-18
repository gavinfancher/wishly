---
title: Overview
description: Practice repo for Postgres backups to S3, secured with Infisical-managed credentials
---

This repo is a sandbox for practicing Postgres backup and restore workflows against S3, using AWS credentials pulled from Infisical instead of hardcoded secrets.

## What's here

- A local `postgres:18.4` container (`docker-compose.yml`) for a disposable practice database
- [Infisical](/infisical) for fetching AWS credentials at runtime
- [File-based backups](/backups) (`backup.py`, `backup_flow.py`) that dump to a temp file, upload, then clean up
- [Streaming backups](/streaming-backups) (`backup_stream.py`) that pipe `pg_dump` straight into S3, no temp files
- [Restore](/restore) (`restore.py`) that pulls the most recent backup from S3 and replays it

## Quick start

```bash
docker compose up -d
uv run backup_stream.py
uv run restore.py
```
