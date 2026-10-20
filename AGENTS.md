# Wishly

Wishly is a simple app I'm using as a project to work on my systems engineering skills. The
app is a small front end where users create an account and add events they'd like to be
reminded of, then get a customized reminder cadence over email. E.g. I want to be reminded a
week ahead of my mom's birthday so I can make dinner reservations, and again the day of so I
can call her.

## Tech stack

- **Frontend** — static site on Cloudflare Pages.
- **Auth** — our own email + password sessions in the API. 8-character minimum, no
  password resets (planned: split out into its own auth microservice).
- **API** — FastAPI (Python), one self-contained container, exposed at api.wishly.dev
  via a Cloudflare Tunnel. Secrets live in one hand-made Kubernetes Secret, never in git.
- **Scheduling** — inside the API: a scheduler thread sends everyone's reminders at
  9am Eastern. No external scheduler.
- **Host** — home k3s cluster (`deploy/k8s`), kept in sync by Argo CD. CI builds the
  image on GitHub and commits its tag; Argo rolls it out.
- **Monitoring** — the only thing on AWS: an EventBridge → Lambda watchdog pings a
  key-protected, rate-limited `/internal/ping` every minute and pushes via ntfy after
  5 minutes down.
- **Email** — Resend, plain text.
- **Database** — self-hosted Postgres 18 on my home network (moved off PlanetScale
  2026-10). Set up with `infra/sql/roles.sql`, then `infra/sql/schema.sql`.

## Why this project

I want to get into cloud engineering / sales engineering, so I'm using this project to blog
about it and to build cost-effective, higher-availability setups.

## Where it's going

v3 (see `v3.md`) is the current target: the app on the home k8s cluster with Argo CD as
the CD. AWS stays limited to the watchdog Lambda; there is no AWS failover.
