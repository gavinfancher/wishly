# Secrets

Infisical is the source of truth and its only job is to **sync into AWS Secrets
Manager**. Nothing renders a `.env` from it any more. Every runtime — laptop, VM,
ECS — reads the same secret, `wishly/prod`, through the same code.

```
   Infisical  ──sync──▶  Secrets Manager: wishly/prod  ──▶  container entrypoint
   (edit here)           (one JSON document)                (boto3, at startup)
```

`infra/.env` holds only what is needed to *reach* AWS: which secret, and
credentials where the host is not in AWS. The region is fixed at `us-east-1` in
`bootstrap.py` — every Wishly resource lives there. That is the same shape an
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

**3. Keep Infisical to actual secrets.** The synced document needs every value the
app cannot default. It does not need deployment constants: `APP_BASE_URL`,
`ALLOWED_ORIGINS`, `CLERK_FRONTEND_API` and `EMAIL_FROM` now default to their
production values in `core/settings.py`, so they belong in code, not in a secret
store. Override them in `infra/.env` when you want a local frontend.

`ENVIRONMENT` is the one deployment fact worth setting explicitly — it is the
switch the checks below key off.

You do not have to take any of this on trust. At `ENVIRONMENT=prod` the app
refuses to start when a required secret is missing, or when a deployment constant
has been overridden back to a localhost value, and it names them:

```
ENVIRONMENT=prod but these are unset or still at their development default:
clerk_secret_key, resend_api_key. Add them to the secret this process loads
(see infra/secrets.md), or run with ENVIRONMENT=dev.
```

`TRIGGER_TOKEN` is required in production. It is the shared secret on the
`X-Wishly-Trigger` header: EventBridge sends it on the hourly tick and the
detector Lambda sends it on every liveness probe. **It is also set independently
in `infra/terraform/terraform.tfvars`, and nothing reconciles the two.** Set them
to the same string; a mismatch stops every reminder and the only symptom is a
403 a minute in the detector's log.

`TAILSCALE_API_KEY` is no longer read by anything — the detector probes our own
API now — and can go. `SLACK_WEBHOOK_URL` stays: the detector still posts there
when it fails over.

`PREFECT_API_URL`, `PREFECT_API_KEY`, `PREFECT_SERVER_DATABASE_CONNECTION_URL`
and `PREFECT_WORK_POOL` can all go with it.

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
