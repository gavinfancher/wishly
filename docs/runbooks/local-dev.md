# Local development

How to run Wishly on your machine, from "no backend at all" up to "real Clerk, real
Postgres, two origins". Pick the lowest tier that covers what you're working on —
each one costs more setup than the last.

| Tier | What runs | Use it for |
|---|---|---|
| 1. Mock | Vite only | UI work, layout, copy |
| 2. Real API | Vite + FastAPI + Postgres, auth bypassed | endpoints, queries, data shape |
| 3. Real Clerk | as above, plus Clerk | sign-in / sign-up flows, tokens |
| 4. Two origins | as above, on `:5173` + `:5174` | the `wishly.dev` / `app.wishly.dev` split |

Backend commands run from `backend/` (its own uv project); frontend commands from
`frontend/`. The full containerised stack is one compose invocation — see the
bottom of this page.

---

## Tier 1 — mock mode (no backend)

`frontend/.env` ships this way. `VITE_MOCK_API=true` serves seeded data from an
in-browser mock and `VITE_DEV_NO_AUTH=true` signs you in as a fixed "Dev User",
so Clerk and Postgres are both unnecessary.

```bash
cd frontend && npm run dev      # http://localhost:5173
```

Everything renders populated. No Clerk key required.

---

## Tier 2 — real API, auth still bypassed

Start Postgres, migrate, seed, and run FastAPI:

```bash
docker compose -f infra/compose.yaml -f infra/compose.local.yaml --env-file infra/.env up -d postgres
cd backend && uv run alembic upgrade head
cd backend && uv run python -m wishly.db.seed
cd backend && uv run uvicorn wishly.api.main:app --reload   # http://localhost:8000
```

In `backend/.env` (copy from `infra/.env.example`):

```bash
DATABASE_URL=postgresql://wishly:wishly@localhost:5432/wishly
AUTH_DEV_BYPASS=true
ENVIRONMENT=dev
```

In `frontend/.env`:

```bash
VITE_MOCK_API=false
VITE_API_BASE_URL=http://localhost:8000
VITE_DEV_NO_AUTH=true
```

`AUTH_DEV_BYPASS` makes every request authenticate as a fixed local user
(`user_dev_local` / `dev@wishly.local`). It is ignored when `ENVIRONMENT=prod`,
so it cannot weaken a real deployment even if the flag leaks into a prod env file.

Both sides must agree: `VITE_DEV_NO_AUTH` and `AUTH_DEV_BYPASS` are flipped
together, or the frontend sends a placeholder token to a backend that verifies it.

---

## Tier 3 — real Clerk

Clerk **development** instances accept `http://localhost` origins as-is, so no
tunnel or custom domain is needed.

1. In the Clerk dashboard, create an application (or open the existing one).
2. **API Keys** gives you both keys and the Frontend API host.

`frontend/.env`:

```bash
VITE_CLERK_PUBLISHABLE_KEY=pk_test_...   # real key, not the placeholder
VITE_DEV_NO_AUTH=false
```

`backend/.env`:

```bash
CLERK_SECRET_KEY=sk_test_...
CLERK_FRONTEND_API=https://<your-slug>.clerk.accounts.dev
AUTH_DEV_BYPASS=false
```

`CLERK_FRONTEND_API` is the token issuer; the backend derives the JWKS URL from
it (or set `CLERK_JWKS_URL` outright). Restart both servers — Vite only reads
`.env` at startup.

What you should see at `http://localhost:5173`:

- **Login** (top right) → `/sign-in`, Clerk's `<SignIn>` component, including the
  "Don't have an account? Sign up" link — that link exists because the component
  is passed `signUpUrl="/sign-up"`.
- **Get started** → `/sign-up`, Clerk's `<SignUp>` component.
- After either flow, Clerk redirects to `DASHBOARD_URL` (see below).

Webhooks (`/webhooks/clerk`) are the one thing localhost can't receive. Either
skip them at this tier or point a tunnel at `localhost:8000`.

---

## Tier 4 — two origins (`wishly.dev` + `app.wishly.dev`)

In production the marketing page and the dashboard are one build served from two
hosts. Locally, two ports stand in for the two subdomains:

```bash
cd frontend && npm run dev                  # marketing, stands in for wishly.dev
cd frontend && npm run dev -- --port 5174   # dashboard, stands in for app.wishly.dev

# without just, from frontend/:
npm run dev
npm run dev -- --port 5174
```

`frontend/.env`:

```bash
VITE_APP_BASE_URL=http://localhost:5174
```

`backend/.env` — the second origin calls the API too, so CORS must allow it:

```bash
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:5174
```

Now **Login** on `:5173` renders as a real `<a href="http://localhost:5174/app">`
and performs a full cross-origin navigation, the same as it will in production.
Leave `VITE_APP_BASE_URL` empty and the link collapses back to a client-side
route to `/app` on whichever port you're already on.

**Why ports are a fair stand-in for subdomains:** cookies ignore port numbers, so
a Clerk session set on `localhost:5173` is sent to `localhost:5174` automatically.
In production the equivalent is Clerk setting its cookie on the apex domain and
both `wishly.dev` and `app.wishly.dev` reading it — provided both hosts are
registered on the Clerk instance.

The one thing this does *not* reproduce: ports are same-origin for cookies but
cross-origin for CORS, whereas the real subdomains are cross-origin for both. If
CORS works locally it will work in production; the reverse isn't guaranteed.

---

## Everyday commands

```bash
docker compose -f infra/compose.yaml -f infra/compose.local.yaml --env-file infra/.env up -d postgres   # data survives `down`
cd backend && uv run alembic upgrade head
cd backend && uv run ruff check . && uv run mypy src
cd backend && uv run pytest      # needs the wishly_test database
cd backend && uv run uvicorn wishly.api.main:app --reload
cd backend && uv run python -m wishly.orchestration.flows   # send flow, once
cd frontend && npm run dev
```

Frontend checks run from `frontend/`:

```bash
npm run lint && npm run typecheck && npm run build
```

---

## Troubleshooting

**"Wishly needs local configuration" screen.** `frontend/.env` is missing or
`VITE_CLERK_PUBLISHABLE_KEY` is still `pk_test_replace_me`. Either put a real key
in, or set `VITE_DEV_NO_AUTH=true` to skip Clerk.

**Env change had no effect.** Vite reads `.env` at startup only. Restart it.

**CORS errors after adding the second origin.** `ALLOWED_ORIGINS` is a
comma-separated list read by `backend/src/wishly/core/settings.py`; it defaults to
`http://localhost:5173` alone. Add `:5174` and restart the API.

**Signed in on `:5173`, signed out on `:5174`.** Expected if the two servers were
built with different `VITE_CLERK_PUBLISHABLE_KEY` values — they must share one
Clerk instance to share a session.

---

## The whole stack in containers

Everything the server runs — API, Postgres, Prefect server + worker, and the
Cloudflare tunnel — in one command:

```bash
docker compose -f infra/compose.yaml -f infra/compose.local.yaml --env-file infra/.env up -d
```

`compose.local.yaml` is an **overlay**, not a stack: it only adds loopback-published
ports and a separate Postgres volume, so both `-f` flags are required. `infra/.env`
is rendered by the Infisical agent (docs/runbooks/secrets.md).

**Tests never use the development database.** `backend/tests/conftest.py` truncates
every table and refuses to start unless `DATABASE_URL` names a database ending in
`_test`. Create it once with `create database wishly_test owner wishly` and migrate it.
