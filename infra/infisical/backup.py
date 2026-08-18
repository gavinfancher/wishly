import os
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

try:
    subprocess.run(
        [
            "docker", "exec", CONTAINER,
            "pg_dump", "-U", DB_USER, "-d", DB_NAME, "-F", "c", "-f", f"/tmp/{filename}",
        ],
        check=True,
    )
    subprocess.run(
        ["docker", "cp", f"{CONTAINER}:/tmp/{filename}", filename],
        check=True,
    )

    s3 = boto3.resource(
        "s3",
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
        region_name="us-east-1"
    )

    s3.Bucket(BUCKET).upload_file(
        Filename=filename,
        Key=f"backups/{filename}"
    )

    print(f"Uploaded s3://{BUCKET}/backups/{filename}")
finally:
    subprocess.run(["docker", "exec", CONTAINER, "rm", "-f", f"/tmp/{filename}"])
    if os.path.exists(filename):
        os.remove(filename)
