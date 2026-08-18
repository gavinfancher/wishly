---
title: Backups
description: Dumping the database to a file and uploading it to S3
---

`backup.py` takes a full database dump (schema + data, every table) and uploads it to S3, using [Infisical-sourced credentials](/infisical).

## How it works

1. `docker exec` runs `pg_dump -F c` **inside** the container, so the client version always matches the server, writing to `/tmp/<db>-<timestamp>.dump`
2. `docker cp` pulls that file out to the repo directory
3. `boto3` uploads it to `s3://wishly-dev-01/backups/<file>`
4. A `finally` block removes the file from both the container's `/tmp` and the local directory, whether the run succeeded or failed

```bash
uv run backup.py
```

`-F c` (custom format) is compressed and restorable with `pg_restore`, including parallel or selective restores — unlike a plain SQL dump.

## Multiple tables

`pg_dump -d <database>` (no `-t` flag) dumps every table in the database in dependency order. Nothing extra is needed to back up more than one table — you'd only add `-t <table>` if you wanted a single-table dump instead.

## Orchestrating with Prefect

`backup_flow.py` wraps the same dump/upload steps as Prefect `@task`s inside a `@flow`, for retries and run history:

```bash
PREFECT_API_URL="" uv run backup_flow.py
```

The `PREFECT_API_URL=""` override forces Prefect's local ephemeral server instead of whatever Prefect Cloud workspace your global config points at.
