---
title: Streaming backups
description: Piping pg_dump directly into S3 with no local temp files
---

`backup_stream.py` is a leaner version of [`backup.py`](/backups): it never writes the dump to disk anywhere, in the container or locally.

## How it works

`pg_dump` runs as a subprocess with its stdout piped directly into `boto3`'s `upload_fileobj`, which streams it to S3 (handling multipart upload internally):

```python
proc = subprocess.Popen(
    ["docker", "exec", CONTAINER, "pg_dump", "-U", DB_USER, "-d", DB_NAME, "-F", "c"],
    stdout=subprocess.PIPE,
)

s3.upload_fileobj(proc.stdout, BUCKET, key)
```

```bash
uv run backup_stream.py
```

## Why prefer this

- No temp files to clean up in the container or the repo, so there's nothing to leak if a step fails partway
- Nothing is buffered twice (once in the container, once locally) before reaching S3
- Fewer moving parts than `backup.py` — no `docker cp`, no local file path bookkeeping

## Auth is unchanged

Streaming only changes how the *bytes* move — the S3 client authenticates exactly the same way as every other script, using `aws_access_key` / `aws_secret_key` from [`get_secrets.py`](/infisical). `docker exec` itself talks to the local Docker socket and needs no AWS credentials at all.
