# Wishly

Pick a date, pick how many days before it you want an email. Wishly sends a
plain-text reminder at 9am Eastern, every year.

This repo is the whole thing: the API, the frontend, and the infrastructure to
run them. Following this page, you can bring up your own copy from nothing.

```
backend/          FastAPI app → one self-contained Docker image on GHCR
frontend/         React app → Cloudflare Pages
deploy/k8s/       what runs in the cluster: the API and cloudflared
deploy/argocd/    the Argo CD Application that keeps the cluster matching deploy/k8s
infra/postgres/   the production Postgres: one Compose file for its Docker host
infra/sql/        roles.sql (one-time database + roles), schema.sql (the tables)
infra/terraform/  Cloudflare Tunnel + DNS
docs/design.md    how the app works
docs/infrastructure.md  how it runs: every piece, secret, and failure mode
```

## How the pieces connect

- **The API** is one container that does everything: serves the frontend's API
  at `api.<domain>`, and sends the day's reminders itself at 9am Eastern. No
  external scheduler.
- **Postgres** runs in Docker on its own box on your network
  (`postgres.ad.gavinf.com`, from `infra/postgres/compose.yaml`);
  `infra/sql/roles.sql` creates the database and its two roles.
- **Kubernetes** (k3s at home) runs the API and two cloudflared connectors.
  Cloudflare Tunnel carries `api.<domain>` in; nothing at home is exposed.
- **Secrets** live in Infisical (project `wishly-tg-hh`, env `prod`). The cluster's
  Infisical operator copies them into one Kubernetes Secret, `wishly`
  (`deploy/k8s/infisical-secret.yaml`). Nothing secret is committed or baked
  into the image.
- **On every merge to `main`**, CI tests and builds `ghcr.io/<you>/wishly:<sha>`,
  then commits that tag to `deploy/k8s/kustomization.yaml`. **Argo CD** sees the
  commit and rolls the cluster.
- **Terraform** creates the Cloudflare Tunnel and its DNS record, nothing else.
  Its state lives in an S3 bucket.

## Bring up your own

### 0. Accounts and tools

Accounts: AWS, Cloudflare (with a domain on it), Resend, GitHub.
Tools on your laptop: `terraform` ≥ 1.11, `kubectl`, `jq`, `aws`, `uv`, Docker.
A Kubernetes cluster with Argo CD installed (in the `argocd` namespace), and a
Docker host on the same network for Postgres. Keep every password this guide
generates in your password manager.

Use an AWS IAM user or SSO for the CLI, never the account's root keys.

### 1. The image

Fork this repo and push to `main`. `.github/workflows/api.yml` runs the tests,
publishes `ghcr.io/<you>/wishly:<sha>`, and commits that tag to
`deploy/k8s/kustomization.yaml`. In GitHub → Packages → wishly → settings, make
the package public so the cluster can pull it without credentials.

If `main` is branch-protected, allow GitHub Actions to push to it, or the
release job's tag commit is rejected.

### 2. Terraform state bucket (once)

Terraform can't create the bucket it keeps its own state in, so make it by hand:

```bash
bucket=<you>-wishly-tf-state
aws s3api create-bucket --bucket "$bucket" --region us-east-1
aws s3api put-bucket-versioning --bucket "$bucket" --versioning-configuration Status=Enabled
aws s3api put-public-access-block --bucket "$bucket" \
  --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```

### 3. Terraform

```bash
cd infra/terraform
cp backend.hcl.example backend.hcl            # your bucket name
cp terraform.tfvars.example terraform.tfvars  # your domain and Cloudflare IDs

# Provider credentials, from each service's dashboard:
export AWS_PROFILE=...                         # for the state bucket only
export CLOUDFLARE_API_TOKEN=...                # Tunnel: Edit, DNS: Edit

terraform init -backend-config=backend.hcl
terraform plan
terraform apply
```

### 4. Database

Start Postgres on its host (here `postgres.ad.gavinf.com`, any Docker host the
cluster can reach), with a superuser password that only exists on that box:

```bash
DB=postgres.ad.gavinf.com
ssh ubuntu@$DB 'sudo install -d -o ubuntu -m 0750 /opt/postgres'
scp infra/postgres/compose.yaml ubuntu@$DB:/opt/postgres/
ssh ubuntu@$DB 'cd /opt/postgres && umask 077 &&
  { [ -f .env ] || echo "POSTGRES_PASSWORD=$(openssl rand -hex 24)" > .env; } &&
  docker compose up -d --wait && docker compose ps'
```

Then create the database and its two roles (`infra/sql/roles.sql`), and the
tables as the schema role (`infra/sql/schema.sql`). Read both first. Run these in
one shell, so the passwords carry through to step 5:

```bash
SUPER_PW=$(ssh ubuntu@$DB 'sed -n "s/^POSTGRES_PASSWORD=//p" /opt/postgres/.env')
APP_PW=$(openssl rand -hex 24) SCHEMA_PW=$(openssl rand -hex 24)

docker run --rm -i postgres:18.4 psql "postgresql://postgres:$SUPER_PW@$DB:5432/postgres" \
  -v ON_ERROR_STOP=1 -v app_password="$APP_PW" -v schema_password="$SCHEMA_PW" \
  < infra/sql/roles.sql
docker run --rm -i postgres:18.4 psql "postgresql://wishly_schema:$SCHEMA_PW@$DB:5432/wishly" \
  -v ON_ERROR_STOP=1 < infra/sql/schema.sql

echo "wishly_app: $APP_PW   wishly_schema: $SCHEMA_PW"   # into your password manager
```

Both SQL files are safe to re-run. They only create what's missing.

### 5. The cluster

The cluster needs the Infisical operator and its machine identity (set up in
the homek8s repo), with that identity a viewer on the Wishly Infisical project.
In its **Production** env, at the root, add these keys:

| Key | Value |
|---|---|
| `WISHLY_DATABASE_URL` | `postgresql://wishly_app:<APP_PW>@<DB>:5432/wishly` |
| `WISHLY_RESEND_API_KEY` | from Resend |
| `TUNNEL_TOKEN`, `WISHLY_CORS_ORIGINS` | `terraform -chdir=infra/terraform output -json cluster_secret_values` |
| `WISHLY_SIGNUP_ENABLED` | optional; `false` once your account exists |

`deploy/k8s/infisical-secret.yaml` turns them into the `wishly` Secret.

Then hand `deploy/k8s` to Argo CD. From here on, git is the deploy tool:

```bash
kubectl apply -f deploy/argocd/wishly.yaml
kubectl -n wishly get pods -w     # 3 wishly-api + 3 cloudflared, one of each per worker
```

### 6. Check it

```bash
curl https://api.<your-domain>/healthz   # {"status":"ok","version":"<sha>"}
curl https://api.<your-domain>/readyz    # {"status":"ready"}
```

### 7. Frontend

Create a Cloudflare Pages project from `frontend/` with these build variables:
`VITE_API_BASE_URL=https://api.<your-domain>/v1`. Then sign up at
`https://<your-domain>/sign-up`, then set `WISHLY_SIGNUP_ENABLED=false` in
Infisical so nobody else can. The operator restarts the API within a minute.

## Day to day

- **Ship code:** merge to `main`. CI tests, builds, and commits the new tag;
  Argo CD rolls it out within a few minutes. Watch it in the Argo CD UI or with
  `kubectl -n wishly rollout status deploy/wishly-api`.
- **Roll back:** revert the `deploy: wishly <sha>` commit (or set `newTag` to an
  older SHA) and push. Argo applies it like any other change.
- **Change a secret:** edit it in Infisical. Within a minute the operator
  updates the `wishly` Secret and restarts the pods that read it.
- **Change the schema:** edit `infra/sql/schema.sql`, review it, re-run it as in
  step 4.
- **Change infrastructure:** `deploy/k8s` via git (Argo applies it);
  `infra/terraform` via `plan` and `apply`.

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

`kubectl delete -f deploy/argocd/wishly.yaml` removes Wishly from the cluster
(prune deletes everything it created), then `terraform destroy` removes the
tunnel and DNS. The database is yours to drop by hand.
