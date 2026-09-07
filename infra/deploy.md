# Deploying a change

One image, one architecture (amd64), one tag. The VM and the ECS standby pull
the **same digest**, so what you test is what fails over.

```
  laptop                    ECR                  VM              ECS
  ------                    ---                  --              ---
  images.sh --push  ──▶  wishly-api:<sha>  ──▶  compose pull  ──▶ terraform apply
                         wishly-worker:<sha>
```

## 1. Build and push

From a clean checkout — the script refuses a dirty tree, because a tag naming a
commit that does not describe the bytes is worse than no tag:

```bash
git push                       # commit first
./infra/images.sh --push       # tags with the short SHA, prints each digest
```

## 2. Roll the VM

```bash
ssh ubuntu@wishly-vm 'cd ~/wishly && git pull && \
  sed -i "s/^WISHLY_TAG=.*/WISHLY_TAG=<sha>/" infra/.env && \
  docker compose -f infra/compose.yaml --env-file infra/.env pull && \
  docker compose -f infra/compose.yaml --env-file infra/.env up -d'
```

`git pull` is for compose.yaml and the schema, not the app code — the code
arrives inside the image.

Recreate cloudflared alongside the API if the API container is replaced: it runs
in the API's network namespace, so a new API container orphans it.

## 3. Roll the ECS standby

```bash
cd infra/terraform
sed -i '' 's/^image_tag.*/image_tag = "<sha>"/' terraform.tfvars
terraform apply
```

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
