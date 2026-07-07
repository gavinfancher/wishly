# T7.4 — Cloudflare Pages Deployment Runbook

Deploy the `frontend/` React + Vite SPA to Cloudflare Pages at `wishly.dev`, including
SPA fallback routing, environment variables, and custom domain binding.

---

## Prerequisites

- The `wishly.dev` zone is in your Cloudflare account
- The repo is hosted on GitHub (or GitLab) and you have admin access
- `frontend/` passes `npm run build` locally (T6.4 complete)
- `VITE_CLERK_PUBLISHABLE_KEY` is available (from Clerk dashboard, Task T2.1 / §10)
- `VITE_API_BASE_URL` is `https://api.wishly.dev` (tunnel must be live, T7.3)

---

## Step 1 — Add SPA fallback routing file

Cloudflare Pages serves the `_redirects` file from the build output root. For a Vite project,
place the file in `frontend/public/` so Vite copies it verbatim to `frontend/dist/` during the
build.

Create `frontend/public/_redirects` with exactly this content (one line):

```
/* /index.html 200
```

- `/*` matches every path
- `/index.html 200` rewrites to the SPA entry point with a 200 status (not an HTTP redirect)
- The browser URL stays unchanged; React Router handles client-side routing

This file must be at `frontend/public/_redirects`, not `frontend/src/` or `frontend/dist/`
(the `dist/` directory is the build output and should not be committed).

Commit this file to the repo before deploying.

---

## Step 2 — Pin Node.js version

Cloudflare Pages build system v3 defaults to Node 22. Pin to Node 20 LTS (as specified in
PLAN §2) by creating `frontend/.nvmrc`:

```
20
```

Cloudflare Pages reads `.nvmrc` and selects that major version. This file also works in local
dev with nvm/fnm.

Alternatively, you can set the `NODE_VERSION=20` environment variable in the Pages dashboard
(see step 4), but the file-based approach is more portable.

---

## Step 3 — Connect the repo to Cloudflare Pages

1. Log in to **dash.cloudflare.com**
2. In the left sidebar, click **Workers & Pages**
3. Click **Create application** → select the **Pages** tab → click **Connect to Git**
4. Authorise Cloudflare to access your GitHub account (or organisation) if not already done.
   Grant access to the `wishly` repository (you can scope access to only this repo)
5. Select the `wishly` repository and click **Begin setup**
6. Fill in the build configuration:

| Field | Value |
|---|---|
| Project name | `wishly` (this sets the `wishly.pages.dev` preview URL) |
| Production branch | `main` |
| Framework preset | `None` (or `Vite` if available) |
| Build command | `npm run build` |
| Build output directory | `dist` |
| Root directory | `frontend` |

The **Root directory** must be `frontend` because the repo root is the monorepo root, not the
frontend package root. Cloudflare Pages sets the working directory to `frontend/` before running
the build command.

7. Do **not** click Save yet — proceed to step 4 to set environment variables first.

---

## Step 4 — Set environment variables

Still on the "Set up builds and deployments" page, expand the **Environment variables** section.
Add the following for the **Production** environment:

| Variable | Value |
|---|---|
| `VITE_CLERK_PUBLISHABLE_KEY` | Your Clerk publishable key (starts with `pk_live_...`) |
| `VITE_API_BASE_URL` | `https://api.wishly.dev` |

These are build-time variables. Vite embeds them into the compiled output (`import.meta.env.VITE_*`).
They are not secrets, but Cloudflare lets you mark them as encrypted if preferred.

To set separate values for preview deployments (PRs / non-main branches), click
**Add variable** under the **Preview** environment section and use a different Clerk key
(e.g. a Clerk dev instance key starting with `pk_test_...`) and a staging API URL if you have one.

Click **Save and Deploy**.

---

## Step 5 — Verify the initial deployment

After clicking Save and Deploy, Cloudflare Pages clones the repo, installs dependencies
(`npm ci` or `npm install`), and runs `npm run build` in the `frontend/` directory.

Watch the build log in the dashboard. A successful build ends with:

```
✓ Built in Xs
Build output directory: dist
✓ Uploading assets...
✓ Deployment complete: https://wishly.pages.dev
```

Visit the preview URL (`https://wishly.pages.dev`) and confirm:

- The app loads at `/`
- Navigating to a deep link (e.g. `/events`) and refreshing the browser returns the SPA (not a
  404) — this confirms the `_redirects` file is working

---

## Step 6 — Add the custom domain (wishly.dev)

1. In the Pages project dashboard, click the **Custom domains** tab
2. Click **Set up a domain**
3. Enter `wishly.dev` and click **Continue**

Because `wishly.dev` is already in your Cloudflare account, Cloudflare automatically creates a
CNAME record pointing `wishly.dev` to `wishly.pages.dev`:

```
wishly.dev  CNAME  wishly.pages.dev  (Proxied)
```

You will be asked to confirm. Click **Activate domain**.

Cloudflare provisions a Universal SSL certificate for `wishly.dev` automatically. HTTPS is
enforced; no manual certificate steps are required.

> **Do not** manually add a CNAME at DNS before completing this flow. Adding the DNS record
> before associating the domain in Pages causes a 522 error.

DNS propagation and certificate provisioning typically complete within **15 minutes**. Visit
`https://wishly.dev` to confirm.

---

## Step 7 — Verify SPA routing on the custom domain

```bash
# Deep link should return 200, not 404
curl -I https://wishly.dev/events
curl -I https://wishly.dev/preferences
```

Both should return `HTTP/2 200`. If you get 404, confirm that `frontend/public/_redirects`
exists and was committed before the last deployment.

---

## Environment variable reference

These are the variables the Cloudflare Pages build reads. All are set in the Pages dashboard
under **Settings → Environment variables** (or in the initial setup flow).

| Variable | Value | Notes |
|---|---|---|
| `VITE_CLERK_PUBLISHABLE_KEY` | `pk_live_...` | From Clerk dashboard → API Keys |
| `VITE_API_BASE_URL` | `https://api.wishly.dev` | Must use the tunnel URL (T7.3) |
| `NODE_VERSION` | `20` | Only needed if not using `frontend/.nvmrc` |

These variables are embedded at build time. Changing them requires a redeploy.

---

## Subsequent deployments

After initial setup, every push to the `main` branch triggers an automatic production deployment.
Every push to a non-main branch triggers a preview deployment at a unique URL
(`https://<hash>.wishly.pages.dev`), useful for reviewing PRs before they reach production.

To redeploy without a code change (e.g. after updating environment variables):

1. **Settings → Builds & deployments → Retry deployment** on the latest production deployment

Or trigger via Wrangler:

```bash
cd frontend
npx wrangler pages deploy dist --project-name wishly
```

---

## Build configuration summary

| Setting | Value |
|---|---|
| Build command | `npm run build` |
| Build output directory | `dist` |
| Root directory | `frontend` |
| Node.js version | `20` (via `.nvmrc`) |
| SPA fallback | `frontend/public/_redirects` → `/* /index.html 200` |
| Custom domain | `wishly.dev` |
| Preview domain | `wishly.pages.dev` |

---

## QUESTIONS

None — the build command, output directory, env var names (`VITE_CLERK_PUBLISHABLE_KEY`,
`VITE_API_BASE_URL`), SPA fallback approach, and custom domain are all specified in PLAN §2,
§10, §11, and T7.4.
