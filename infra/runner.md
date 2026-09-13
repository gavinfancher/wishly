# The build runner

> **Out of date — the image build no longer runs here.** `build.yml` now builds
> on a GitHub-hosted `ubuntu-latest` and pushes to
> `ghcr.io/gavinfancher/wishly:<sha>`, because the repository is public: the
> minutes are free, and a self-hosted runner on a public repo would execute fork
> PR code on the home network — the risk this page's own threat model is about.
>
> Still true and still used: `deploy-vm.yml` runs here (`runs-on: [self-hosted,
> …]`), so the runner is not decommissioned. Everything below describes the ECR
> build that moved; the `wishly-ci` OIDC role in `terraform/oidc.tf` is what
> that build used and nothing assumes it any more. The rest of this page has not
> been rewritten.

A GitHub Actions self-hosted runner on a Proxmox VM. It built both images and
pushed them to ECR whenever `backend/` or the image definitions changed on `main`.

## Why self-hosted, and why it does not open a port

The runner makes an **outbound** long-poll to GitHub and receives jobs over it.
Nothing connects in. That is the whole reason this shape works on a home
network: a Jenkins controller would need GitHub to reach *it*, which means
either exposing a service to the internet or falling back to polling.

It also builds natively on x86_64, keeps a warm Docker layer cache on a machine
you own, and doesn't need your laptop to be awake.

## Why there are no AWS keys on it

The runner assumes `wishly-ci` through GitHub's OIDC provider. Each run gets a
token minted by GitHub, trades it at STS for credentials that expire in an hour,
and stores nothing. The trust policy is pinned to
`repo:gavinfancher/wishly:ref:refs/heads/main` — a workflow on a branch, a fork,
or any other repository cannot assume it.

The role can push to the two ECR repositories and read them back. It cannot
delete images, touch Secrets Manager, or change ECS.

## Provisioning the VM

A small VM is plenty — 2 vCPU, 4 GB RAM, **60 GB disk**. The disk is the part
worth not skimping on: build caches grow without bound.

Keep it separate from `wishly-vm`. CI executes whatever is in the repository and
needs the Docker socket, which is root-equivalent on its host. That should not
share a kernel with the production API.

```bash
# on the runner VM
sudo apt update && sudo apt install -y ca-certificates curl git
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"    # log out and back in for this to take effect
```

Then register it (Settings → Actions → Runners → New self-hosted runner gives a
fresh token; the one below is a placeholder):

```bash
mkdir -p ~/actions-runner && cd ~/actions-runner
curl -o runner.tar.gz -L https://github.com/actions/runner/releases/latest/download/actions-runner-linux-x64.tar.gz
tar xzf runner.tar.gz
./config.sh --url https://github.com/gavinfancher/wishly \
            --token <REGISTRATION_TOKEN> \
            --labels self-hosted,linux,x64 \
            --unattended
sudo ./svc.sh install && sudo ./svc.sh start
```

The workflow targets `runs-on: [self-hosted, linux, x64]`, so those labels must
be present.

## Housekeeping

Layer caches fill the disk silently until a build fails on `no space left`:

```bash
sudo tee /etc/cron.weekly/docker-prune >/dev/null <<'SH'
#!/bin/sh
docker buildx prune -f --filter until=168h
docker image prune -f
SH
sudo chmod +x /etc/cron.weekly/docker-prune
```

## If the repository ever becomes public

Stop and reconsider first. A self-hosted runner on a public repository will
execute code from fork pull requests, on your network, next to your AWS access.
The mitigation is ephemeral runners (`--ephemeral`) plus restricting workflows
to non-fork events — do that before flipping visibility, not after.
