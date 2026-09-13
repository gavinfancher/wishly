# Wishly

Wishly is a simple app I'm using as a project to work on my systems engineering skills. The
app is a small front end where users create an account and add events they'd like to be
reminded of, then get a customized reminder cadence over email. E.g. I want to be reminded a
week ahead of my mom's birthday so I can make dinner reservations, and again the day of so I
can call her.

## Tech stack

- **Frontend** — static site on Cloudflare Pages.
- **Auth** — user accounts through Clerk.
- **API** — FastAPI (Python) in a container, exposed via a Cloudflare Tunnel.
- **Orchestration** — an hourly EventBridge rule calling an endpoint on the API. No
  scheduler of its own.
- **Host** — Proxmox Ubuntu VM running Docker Compose for cloudflared and the API.
- **Email** — Resend.
- **Database** — PlanetScale micro instance for production data. Banking on it not going
  offline, which is fine — I have 2 users.

## Why this project

I want to get into cloud engineering / sales engineering, so I'm using this project to blog
about it and to build cost-effective, higher-availability setups.

## Where it's going

The goal is a container on AWS (maybe even a simple Lambda) that pings the Proxmox VM to see
if it's alive. If it hasn't responded for 3 minutes, it triggers an ECS deployment of the
containers. Not sure yet how to get this part going, but that's the eventual target.
