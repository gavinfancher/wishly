---
title: Infisical
description: How AWS credentials are fetched at runtime instead of stored in .env
---

Instead of putting AWS keys in `.env`, this repo fetches them from [Infisical](https://infisical.com) at runtime via `get_secrets.py`.

## How it works

`get_secrets.py` authenticates with Universal Auth (a client ID + client secret, not a long-lived token) and exchanges those for a short-lived access token:

```python
client = InfisicalSDKClient(host="https://app.infisical.com")

client.auth.universal_auth.login(
    client_id=client_id,
    client_secret=client_secret,
)
```

It then reads two secrets by name from the project's `/` path:

- `aws-iam-pg-backup-service-access-key`
- `aws-iam-pg-backup-service-secret-key`

These belong to an IAM user scoped to backup operations (`s3:PutObject`, `s3:GetObject`, `s3:ListBucket` on `wishly-dev-01`) — not a broad admin credential.

## Required environment variables

Set these in `.env` (never committed — see `.gitignore`):

| Variable | Description |
|---|---|
| `INFISICAL_PROJECT_ID` | The Infisical project to read secrets from |
| `INFISICAL_ENV` | Environment slug, e.g. `dev` |
| `INFISICAL_CLIENT_ID` | Universal Auth client ID |
| `INFISICAL_CLIENT_SECRET` | Universal Auth client secret |

## Using it in a script

Any script that needs AWS access imports the resolved credentials directly:

```python
from get_secrets import aws_access_key, aws_secret_key

s3 = boto3.client(
    "s3",
    aws_access_key_id=aws_access_key,
    aws_secret_access_key=aws_secret_key,
    region_name="us-east-1",
)
```

Every script in this repo (`backup.py`, `backup_stream.py`, `restore.py`, `backup_flow.py`) follows this same pattern — credentials never touch disk, and rotating the underlying AWS key only requires updating Infisical.
