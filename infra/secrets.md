# Secrets

Infisical is the source of truth and its only job is to **sync into AWS Secrets
Manager**. Nothing renders a `.env` from it any more. Every runtime — laptop, VM,
ECS — reads the same secret, `wishly/prod`, through the same code.

```
   Infisical  ──sync──▶  Secrets Manager: wishly/prod  ──▶  container entrypoint
   (edit here)           (one JSON document)                (boto3, at startup)
```

`infra/.env` holds only what is needed to *reach* AWS: which secret, which
region, and credentials where the host is not in AWS. That is the same shape an
ECS task definition has, which is the point — local is a rehearsal of failover,
not a different arrangement.

## Setup (one time, in the Infisical dashboard)

**1. AWS Connection** — Infisical assumes a role rather than holding a key.
Create one with this trust policy (`381492033652` is Infisical's US account; the
External ID is your project id):

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "AWS": "arn:aws:iam::381492033652:root" },
    "Action": "sts:AssumeRole",
    "Condition": {
      "StringEquals": { "sts:ExternalId": "8cbc2c7e-fa27-4e37-b3c9-15642fc8ca08" }
    }
  }]
}
```

Grant it `secretsmanager:{Create,Update,Put,Describe,Get,Tag}*` on
`arn:aws:secretsmanager:us-east-1:<account>:secret:wishly/*`.

**2. Secret Sync** → AWS Secrets Manager, **Many-To-One**, destination
`wishly/prod`, auto-sync on. Many-To-One matters: one secret at $0.40/month
instead of eight, and one thing to reference instead of eight.

**3. Put the whole environment in Infisical.** The synced document has to be
complete, because nothing else contributes to it now. Six values used to be
literals in the deleted `env.vm.tmpl`: `ENVIRONMENT`, `AUTH_DEV_BYPASS`,
`CLERK_FRONTEND_API`, `EMAIL_FROM`, `APP_BASE_URL`, `ALLOWED_ORIGINS`.

You do not have to take this list on trust. At `ENVIRONMENT=prod` the app
refuses to start when any of them is missing or still at a development default,
and names the ones it wants:

```
ENVIRONMENT=prod but these are unset or still at their development default:
allowed_origins, app_base_url, clerk_frontend_api. Add them to the secret this
process loads (see infra/secrets.md), or run with ENVIRONMENT=dev.
```

That check lives in `core/settings.py`. The localhost defaults are the reason
it exists: an unset `ALLOWED_ORIGINS` does not fail, it silently falls back to
`http://localhost:5173` and breaks CORS in production while every health check
stays green.

Delete `PREFECT_SERVER_DATABASE_CONNECTION_URL` and `PREFECT_WORK_POOL` while
you are there — leftovers from self-hosted Prefect.

## How a container gets it

`python -m wishly.bootstrap` is the entrypoint. It reads the secret named by
`WISHLY_SECRETS_ID`, fills in any environment variable not already set, then
execs the real command. Unset that variable and it does nothing.

Credentials are never passed to it explicitly — boto3 resolves them:

| | Credentials | Long-lived keys |
| --- | --- | --- |
| ECS | task role, via the container credentials endpoint | none; AWS rotates them |
| Laptop / VM | `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` in `.env` | yes — neither host is in AWS, so neither can have a role |

That row is the only difference between local and ECS. Scope the IAM user to one
action on one secret — the same single statement the ECS task role gets:

```json
{
  "Effect": "Allow",
  "Action": "secretsmanager:GetSecretValue",
  "Resource": "arn:aws:secretsmanager:us-east-1:<account>:secret:wishly/prod-*"
}
```

The trailing `-*` is not optional: Secrets Manager appends six random characters
to the ARN, so `...:secret:wishly/prod` matches nothing.

## Running it

```bash
cp infra/.env.example infra/.env    # fill in the keys and TUNNEL_TOKEN
docker compose -f infra/compose.yaml --env-file infra/.env up -d
```

Rotating a secret in Infisical propagates to Secrets Manager on its own, but a
running container keeps the values it started with. Restart to pick them up —
on ECS that is `aws ecs update-service --force-new-deployment`.

## The one exception

`cloudflared` is Cloudflare's image, so it has no entrypoint of ours and cannot
load anything. `TUNNEL_TOKEN` therefore stays in `.env` locally, and on ECS the
task definition injects it into that container natively from the same secret.
