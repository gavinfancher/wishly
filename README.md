# Wishly

Pick a date, pick how many days before it you want an email. Wishly sends a
plain-text reminder at your chosen hour, every year.

This repo is the whole thing: the API, the frontend, and the infrastructure to
run them. Following this page, you can bring up your own copy from nothing.

```
backend/          FastAPI app → one Docker image on GHCR
frontend/         React app → Cloudflare Pages
infra/sql/        the database schema, one readable SQL file
infra/terraform/  PlanetScale, Cloudflare Tunnel + DNS, the hourly EventBridge trigger
infra/ansible/    turns a fresh VM into a Wishly host + GitHub Actions runner
infra/compose.yaml  what runs on that VM: the API + cloudflared
docs/design.md    how the app works
docs/infrastructure.md  how it runs: every piece, secret, and failure mode
```

## How the pieces connect

- **Terraform** creates the database, its two roles, the tunnel, DNS and the
  hourly trigger, and prints the credentials it made.
- **You** paste those into **Infisical**, which is the one place secrets live.
- **Ansible** installs Docker, the Infisical CLI and a GitHub Actions runner on
  the VM, and drops in `compose.yaml` plus `deploy.sh`.
- **On every merge to `main`**, CI tests and builds the image, then the runner
  on the VM runs `deploy.sh`: `infisical run -- docker compose up -d --wait`.
  Containers get their secrets straight from Infisical; nothing secret is
  committed or written into a config file.

## Bring up your own

### 0. Accounts and tools

Accounts: AWS, Cloudflare (with a domain on it), PlanetScale, Infisical, Clerk,
Resend, GitHub. Tools on your laptop: `terraform` ≥ 1.11, `uv` (runs Ansible
via `uvx`), `aws`, and Docker.

Use an AWS IAM user or SSO for the CLI, never the account's root keys.

### 1. The image

Fork this repo and push to `main`. `.github/workflows/api.yml` runs the tests,
then publishes `ghcr.io/<you>/wishly:<sha>` and `:latest`. In GitHub → Packages
→ wishly → settings, make the package public so the VM can pull it without
logging in.

### 2. Terraform state bucket (once)

Terraform can't create the bucket it keeps its own state in, so make it by hand:

```bash
bucket=<you>-wishly-tf-state
aws s3api create-bucket --bucket "$bucket" --region us-east-1
aws s3api put-bucket-versioning --bucket "$bucket" --versioning-configuration Status=Enabled
aws s3api put-public-access-block --bucket "$bucket" \
  --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```

### 3. Infisical

1. Create a project with a `prod` environment. Note its project ID.
2. Add `WISHLY_RESEND_API_KEY` (from Resend's dashboard). The rest come from
   Terraform in step 4.
3. Create a machine identity (Universal Auth) with **read-only** access to the
   project. It lives on the VM and is what `deploy.sh` logs in as.

### 4. Terraform

```bash
cd infra/terraform
cp backend.hcl.example backend.hcl            # your bucket name
cp terraform.tfvars.example terraform.tfvars  # your org, domain, IDs, image

# Provider credentials, from each service's dashboard:
export AWS_PROFILE=...                         # or AWS_ACCESS_KEY_ID / _SECRET
export CLOUDFLARE_API_TOKEN=...                # Tunnel: Edit, DNS: Edit
export PLANETSCALE_SERVICE_TOKEN_ID=... PLANETSCALE_SERVICE_TOKEN=...

terraform init -backend-config=backend.hcl
terraform plan
terraform apply

terraform output -json infisical_values   # add each of these to Infisical (prod)
```

### 5. Database schema

Read `infra/sql/schema.sql`, then apply it with the schema role:

```bash
infisical run --env=prod -- sh -c \
  'docker run --rm -i postgres:18.4 psql "$WISHLY_SCHEMA_DATABASE_URL" -v ON_ERROR_STOP=1' \
  < infra/sql/schema.sql
```

It's safe to re-run. It only creates what's missing.

### 6. The VM

Any Ubuntu or Debian machine you can SSH into, at home or on a cloud provider,
with Tailscale already installed.

```bash
cd infra/ansible
cp inventory.example.ini inventory.ini        # the VM's Tailscale name + your user
export INFISICAL_CLIENT_ID=... INFISICAL_CLIENT_SECRET=...   # the read-only identity
export INFISICAL_PROJECT_ID=...
export GITHUB_REPOSITORY=<you>/wishly   # gh must be logged in as a repo admin
uvx --from ansible-core ansible-playbook site.yml

ssh <vm> /opt/wishly/deploy.sh          # first deploy by hand; CI does it after this
```

The runner now shows under GitHub → Settings → Actions → Runners. **Before
pushing anything else**, go to Settings → Actions → General and set fork pull
request workflows to *Require approval for all external contributors*. On a
public repo, a pull request can edit a workflow to run on your runner. With
approval required, nothing from a stranger runs until you've read it.

### 7. Check it

```bash
curl https://api.<your-domain>/healthz   # {"status":"ok","version":"<sha>"}
curl https://api.<your-domain>/readyz    # {"status":"ready"}
```

### 8. Frontend

Create a Cloudflare Pages project from `frontend/` with these build variables:
`VITE_API_BASE_URL=https://api.<your-domain>/v1` and `VITE_CLERK_PUBLISHABLE_KEY`.

## Day to day

- **Ship code:** merge to `main`. CI tests, builds, and deploys; the job fails
  if the new container doesn't pass its healthcheck.
- **Change the schema:** edit `infra/sql/schema.sql`, review it, run step 5.
- **Change infrastructure:** edit `infra/terraform`, then `plan` and `apply`.

## Local development

```bash
cd backend
docker compose up -d                       # Postgres 18.4 on localhost:5432
cp .env.example .env
docker compose exec -T postgres psql -U postgres -d wishly < ../infra/sql/schema.sql
uv run pytest
uv run uvicorn wishly.main:create_app --factory --reload

cd ../frontend
VITE_MOCK_API=true VITE_DEV_NO_AUTH=true npm run dev   # UI with fake data, no backend
```

## Tearing it down

`terraform destroy` removes everything except the database, which is protected
by `prevent_destroy` in `infra/terraform/database.tf`. Delete that block first
if you really mean it.
