import boto3

from get_secrets import (
    aws_access_key,
    aws_secret_key
)

BUCKET = "wishly-dev-01"

s3 = boto3.resource(
    "s3",
    aws_access_key_id=aws_access_key,
    aws_secret_access_key=aws_secret_key,
    region_name="us-east-1"
)

wishly_bucket = s3.Bucket(BUCKET)


wishly_bucket.upload_file(
    Filename="local_file.txt",      # local path relative to this file
    Key="test_file.txt"             # destination in bucket relative to root
)