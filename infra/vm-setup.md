# Provisioning wishly-vm

What a fresh Proxmox VM needs before `docker compose up -d` works. It is a short
list, but the failure when one item is missing does not name the missing item —
see the trap below.

The application needs nothing from the host: config comes from Secrets Manager
at startup and the code arrives inside the image. So the host only needs enough
to *fetch and run a container*:

1. Docker
2. The `aws` CLI — `ecr-login.sh` shells out to it
3. `infra/.env`
4. A Docker login to ECR

## The trap: IAM permission is not a Docker login

ECR does not accept SigV4 from the Docker daemon. You exchange IAM credentials
for a 12-hour registry token and store it in `~/.docker/config.json`. A fresh VM
has never done that, so the first `up -d` fails like this:

```
pull access denied, repository does not exist or may require authorization:
authorization failed: no basic auth credentials
```

**`no basic auth credentials` means Docker sent nothing at all**, not that
something was rejected. It is not an IAM error and widening the policy will not
fix it. It reads like a permissions problem and is not one — `./infra/ecr-login.sh`
is the fix. Compose also aborts the whole pull set on the first failure, so the
other two images report `Interrupted` / `No such image`; that is noise.

## 1. Docker

```bash
sudo apt update && sudo apt install -y ca-certificates curl git unzip
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"    # log out and back in
```

Group membership matters more than it looks. `docker login` writes to the
invoking user's `$HOME`, so logging in as `ubuntu` and then pulling under `sudo`
puts you back at `no basic auth credentials` — root has its own, empty,
`config.json`.

## 2. The aws CLI

There is no `awscli` package on Ubuntu 24.04. Ubuntu only ever packaged v1 and
has now dropped it, so `apt install awscli` fails with `no installation
candidate`. Use AWS's own installer:

```bash
curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-$(uname -m).zip" -o /tmp/awscliv2.zip
unzip -q /tmp/awscliv2.zip -d /tmp
sudo /tmp/aws/install
aws --version        # aws-cli/2.x
```

`$(uname -m)` resolves to `x86_64` or `aarch64`, both valid in that URL. The
`aws-cli` snap also works, but classic-confinement snaps have a history of
trouble reading files outside `$HOME`, and `ecr-login.sh` pipes a token into
`docker login`.

## 3. infra/.env

Copy `infra/.env.example` and fill in `WISHLY_TAG`, `AWS_ACCESS_KEY_ID`,
`AWS_SECRET_ACCESS_KEY`, and `TUNNEL_TOKEN`. Nothing else belongs here — see
`secrets.md`.

The keys are only ever read out of this file: `ecr-login.sh` greps the two
`AWS_*` lines into its own process, and Compose passes them to the containers
for boto3. Nothing puts them in your interactive shell, which is why a bare
`aws sts get-caller-identity` on a correctly-configured VM still says
`Unable to locate credentials`. That is expected, not a fault. To run ad-hoc
`aws` commands, borrow them the same way the script does:

```bash
eval "$(grep -E '^AWS_(ACCESS_KEY_ID|SECRET_ACCESS_KEY)=' ~/wishly/infra/.env | sed 's/^/export /')"
export AWS_DEFAULT_REGION=us-east-1
```

## 4. Log in and pull

```bash
cd ~/wishly
./infra/ecr-login.sh                                     # "Login Succeeded"
docker compose -f infra/compose.yaml --env-file infra/.env pull
```

Verify you got the same bytes ECR holds, rather than trusting the tag:

```bash
docker image inspect 809000566572.dkr.ecr.us-east-1.amazonaws.com/wishly-api:<tag> \
  --format '{{index .RepoDigests 0}}'
aws ecr describe-images --repository-name wishly-api --image-ids imageTag=<tag> \
  --query 'imageDetails[0].imageDigest' --output text
```

Same digest, or the claim is not true.

## The IAM user

`wishly-secrets-reader`, with two inline policies:

| policy | grants |
| --- | --- |
| `read-wishly-prod` | `secretsmanager:GetSecretValue` on `wishly/prod-*` |
| `pull-wishly-images` | `ecr:GetAuthorizationToken` on `*`, plus `BatchGetImage`, `GetDownloadUrlForLayer`, `BatchCheckLayerAvailability` on the two repositories |

`GetAuthorizationToken` has to be `Resource: "*"` — it is an account-level call,
and pinning it to a repository ARN denies silently. No push and no delete: this
host consumes images, it does not publish them.

`.env.example` describes this user as scoped to one action on one secret. That
is out of date; the ECR policy was added later.

## Cutting over from an existing VM

Do not run a full `up -d` on the new host while the old one is still serving.
Both read the same `TUNNEL_TOKEN`, and a second connector registering on that
token makes Cloudflare balance production traffic across both — half of it
landing on the machine you are still building. Start the stack without the
tunnel first:

```bash
docker compose -f infra/compose.yaml --env-file infra/.env up -d api worker
```

Then stop the old host and bring up `cloudflared` here. Budget the failover
watchdog into the gap: it promotes ECS after roughly three minutes of a missing
host and does not know the outage was deliberate.

## Optional: stop logging in by hand

`docker login` stores the token in plaintext and it expires every 12 hours.
The credential helper mints one per pull instead:

```bash
sudo apt install -y amazon-ecr-credential-helper
mkdir -p ~/.docker
cat > ~/.docker/config.json <<'EOF'
{ "credHelpers": { "809000566572.dkr.ecr.us-east-1.amazonaws.com": "ecr-login" } }
EOF
```

It runs in the Docker **CLI**, not the daemon, so it resolves credentials from
the environment of whoever runs `docker` — which is why step 3's `eval` line
belongs in `~/.bashrc` if you go this route. `deploy-vm.sh` keeps calling
`ecr-login.sh` either way; that just becomes a redundant login.
