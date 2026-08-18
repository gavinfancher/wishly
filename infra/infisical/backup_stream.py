import subprocess
from datetime import datetime, timezone

import boto3

from get_secrets import (
    aws_access_key,
    aws_secret_key
)

BUCKET = "wishly-dev-01"
CONTAINER = "pg-backup-practice"
DB_USER = "practice"
DB_NAME = "practice"

timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
filename = f"{DB_NAME}-{timestamp}.dump"
key = f"backups/{filename}"

s3 = boto3.client(
    "s3",
    aws_access_key_id=aws_access_key,
    aws_secret_access_key=aws_secret_key,
    region_name="us-east-1"
)

proc = subprocess.Popen(
    [
        "docker", "exec", CONTAINER,
        "pg_dump", "-U", DB_USER, "-d", DB_NAME, "-F", "c",
    ],
    stdout=subprocess.PIPE,
)

s3.upload_fileobj(proc.stdout, BUCKET, key)
proc.stdout.close()
returncode = proc.wait()

if returncode != 0:
    raise SystemExit(f"pg_dump failed with exit code {returncode}")

print(f"Uploaded s3://{BUCKET}/{key}")
