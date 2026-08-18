---
title: Restore
description: Pulling the most recent backup from S3 and replaying it
---

`restore.py` finds the newest backup in S3 and restores it into the running container.

## How it works

1. `list_objects_v2` lists everything under `s3://wishly-dev-01/backups/`
2. The object with the latest `LastModified` is selected — no filename parsing needed
3. It's downloaded locally, then `docker cp`'d into the container's `/tmp`
4. `pg_restore --clean --if-exists` replays it into the `practice` database, dropping and recreating existing objects first
5. A `finally` block removes the file from both the container's `/tmp` and the local directory

```bash
uv run restore.py
```

## Example

```
$ uv run restore.py
Restoring s3://wishly-dev-01/backups/practice-20260816T165931Z.dump
Restored practice-20260816T165931Z.dump into database 'practice'
```

`--clean --if-exists` means restoring is safe to re-run even if the table already exists (e.g. after a `DROP TABLE`) — it drops what's there first instead of erroring out.
