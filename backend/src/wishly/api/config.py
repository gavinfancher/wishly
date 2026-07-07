"""API-layer configuration not covered by ``core.settings``.

``core/settings.py`` is owned elsewhere and intentionally not modified here.
This module reads a couple of *optional* Clerk verification knobs directly from
the environment, deriving sensible defaults from ``CLERK_SECRET_KEY`` where
possible. All values are optional: tests inject keys via ``app.state`` and never
need these.

Env vars (all optional):

* ``CLERK_JWKS_URL`` — full JWKS endpoint, e.g.
  ``https://<slug>.clerk.accounts.dev/.well-known/jwks.json``.
* ``CLERK_FRONTEND_API`` / ``CLERK_ISSUER`` — the Frontend API origin used as
  the token issuer; if ``CLERK_JWKS_URL`` is unset it is derived from this.
"""

from __future__ import annotations

import os

# Identity used when the local dev auth bypass is active (see ``dev_auth_bypass``).
DEV_USER_SUB = "user_dev_local"
DEV_USER_EMAIL = "dev@wishly.local"
DEV_USER_FIRST_NAME = "Dev"
DEV_USER_LAST_NAME = "User"


def dev_auth_bypass() -> bool:
    """Whether to skip Clerk verification and authenticate a fixed dev user.

    For running the UI against a real backend **without Clerk**. Honored only
    outside production: requires ``AUTH_DEV_BYPASS`` truthy *and*
    ``ENVIRONMENT`` != ``prod``, so it can never weaken a prod deployment even
    if the flag leaks into a prod env file.
    """
    if os.getenv("AUTH_DEV_BYPASS", "").strip().lower() not in {"1", "true", "yes", "on"}:
        return False
    return (os.getenv("ENVIRONMENT") or "dev").strip().lower() != "prod"


def clerk_frontend_api() -> str | None:
    """The Clerk Frontend API origin (token issuer), if configured."""
    value = os.getenv("CLERK_FRONTEND_API") or os.getenv("CLERK_ISSUER")
    if not value:
        return None
    value = value.rstrip("/")
    if not value.startswith("http"):
        value = f"https://{value}"
    return value


def clerk_issuer() -> str | None:
    """Expected ``iss`` claim for Clerk session tokens (the Frontend API origin)."""
    return clerk_frontend_api()


def clerk_jwks_url() -> str | None:
    """The JWKS endpoint to fetch Clerk's signing keys from.

    Uses ``CLERK_JWKS_URL`` verbatim if set; otherwise derives it from the
    Frontend API origin. Returns ``None`` if neither is configured.
    """
    explicit = os.getenv("CLERK_JWKS_URL")
    if explicit:
        return explicit
    origin = clerk_frontend_api()
    if origin:
        return f"{origin}/.well-known/jwks.json"
    return None
