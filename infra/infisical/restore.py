import os
import subprocess

import boto3

from get_secrets import (
    aws_access_key,
    aws_secret_key
)

BUCKET = "wishly-dev-01"
PREFIX = "backups/"
CONTAINER = "pg-backup-practice"
DB_USER = "practice"
DB_NAME = "practice"

s3 = boto3.client(
    "s3",
    aws_access_key_id=aws_access_key,
    aws_secret_access_key=aws_secret_key,
    region_name="us-east-1"
)

response = s3.list_objects_v2(Bucket=BUCKET, Prefix=PREFIX)
objects = response.get("Contents", [])
if not objects:
    raise SystemExit(f"No backups found under s3://{BUCKET}/{PREFIX}")

latest = max(objects, key=lambda obj: obj["LastModified"])
key = latest["Key"]
filename = key.removeprefix(PREFIX)

print(f"Restoring s3://{BUCKET}/{key}")

try:
    s3.download_file(Bucket=BUCKET, Key=key, Filename=filename)

    subprocess.run(
        ["docker", "cp", filename, f"{CONTAINER}:/tmp/{filename}"],
        check=True,
    )
    subprocess.run(
        [
            "docker", "exec", CONTAINER,
            "pg_restore", "-U", DB_USER, "-d", DB_NAME, "--clean", "--if-exists", f"/tmp/{filename}",
        ],
        check=True,
    )

    print(f"Restored {filename} into database '{DB_NAME}'")
finally:
    subprocess.run(["docker", "exec", CONTAINER, "rm", "-f", f"/tmp/{filename}"])
    if os.path.exists(filename):
        os.remove(filename)
