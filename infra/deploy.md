# Deploying a change

One image, one architecture (amd64), one tag. The VM and the ECS standby pull
the **same digest**, so what you test is what fails over.

```
  git push        CI (GitHub-hosted)          GHCR
  --------        ------------------          ----
  main  ──────▶  build.yml  ──────────▶  wishly:<sha>        nothing pulls this yet
                                                                       │
  ─────────────────────────────────────────────────────────────────────┘
  your laptop           ECR              VM                ECS
  -----------           ---              --                ---
  images.sh --push ▶ :<sha>  ──▶  deploy-vm.sh  ──▶  terraform apply
                   (immutable)      (manual)           (manual)
                                                  registers a task def;
                                                  nothing starts (count 0)
```

## 0. Two registries, mid-migration

**CI no longer produces the image you run.** `.github/workflows/build.yml` builds
on a GitHub-hosted runner and pushes to `ghcr.io/gavinfancher/wishly:<sha>`,
which is free, holds no long-lived credential, and does not run fork code on the
home network (see `runner.md`). But the VM's `compose.yaml` and the ECS task
definition still name ECR, and nothing yet pulls from GHCR.

So **step 1 is no longer a fallback — it is the deploy.** Until ECR is retired or
ECS and compose are pointed at GHCR, a commit is only deployable after you have
run `images.sh --push` from a checkout yourself.

The trap this sets: `terraform apply -var image_tag=<sha>` succeeds whether or
not that tag exists in ECR. Terraform does not check, and the service sits at
desired-count 0, so nothing tries to pull until a real failover does — and then
it cannot start. **Confirm the tag is in ECR before you apply it** (step 3 has
the command). Pointing ECS at the now-public GHCR package is a one-line change
that removes this whole class of mistake; it has not been made yet.

**CI stops at the registry.** It does not roll the VM (that is a manual
`workflow_dispatch`, because the watchdog fails over on ~3 minutes of downtime)
and it cannot touch ECS at all — Terraform state is local to your laptop and
gitignored, so there is nothing for a runner to apply against. Moving that to an
S3 backend is the prerequisite for automating step 3, and it has not been done.

## 1. Build and push to ECR (required)

From a clean checkout — the script refuses a dirty tree, because a tag naming a
commit that does not describe the bytes is worse than no tag:

```bash
git push                       # commit first
./infra/images.sh --push       # tags with the short SHA, prints the digest
```

One image now, not two. The Prefect worker container is gone — the hourly send
is an EventBridge rule POSTing to `/internal/runs/send-reminders` on the API, so
there is nothing else to build. See `terraform/schedule.tf`.

## 2. Roll the VM

```bash
ssh ubuntu@wishly-vm 'cd ~/wishly && git pull && ./infra/deploy-vm.sh <sha>'
```

`deploy-vm.sh` authenticates to ECR, pins `WISHLY_TAG`, pulls before it swaps,
recreates cloudflared (it shares the API's network namespace, so a replaced API
container orphans it), waits for the health check, and prints the running
digests. Same script whether you run it, the runbook does, or CI does.

`git pull` is for compose.yaml and the schema, not the app code — the code
arrives inside the image.

Provisioning a *new* VM — Docker, the aws CLI, `infra/.env`, and the ECR login
that has to happen before any of this works — is `vm-setup.md`.

## 3. Roll the ECS standby

```bash
cd infra/terraform
terraform apply -var image_tag=<sha>
```

There is no committed `terraform.tfvars` — copy `terraform.tfvars.example` to
`terraform.tfvars` if you would rather keep the values in a file than pass them
on the command line.

This only registers a new task definition. The service is at `desired_count = 0`,
so nothing restarts — the next failover picks up the new revision.

## Verifying they match

```bash
ssh ubuntu@wishly-vm 'docker image inspect <registry>/wishly-api:<sha> \
  --format "{{index .RepoDigests 0}}"'
aws ecr describe-images --repository-name wishly-api --image-ids imageTag=<sha> \
  --query 'imageDetails[0].imageDigest' --output text
```

Same digest, or the claim is not true.

## Rolling back

Set the previous SHA and repeat. ECR tags are immutable, so an old tag still
names exactly the bytes it always named — there is no `latest` to have moved
underneath you.

## Iterating locally

To build without pushing, while working on a change:

```bash
docker compose -f infra/compose.yaml -f infra/compose.build.yaml \
  --env-file infra/.env up -d --build
```

What that builds is **not** what fails over until `images.sh --push` has run.
