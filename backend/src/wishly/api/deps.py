"""Shared FastAPI dependencies: Clerk JWT auth and the DB session.

Auth model (PLAN §10). The SPA sends the Clerk **session token** as
``Authorization: Bearer <jwt>``. Clerk is configured (dashboard →
"Customize session token") to embed a custom claim so the API can read the
user's identity without a round-trip to Clerk:

.. code-block:: json

    { "email": "{{user.primary_email_address}}",
      "first_name": "{{user.first_name}}",
      "last_name": "{{user.last_name}}" }

We verify the token's **signature** against Clerk's JWKS (RS256), and check the
**issuer** and **expiry**, then extract ``sub`` (the Clerk user id) plus the
custom ``email`` / ``first_name`` / ``last_name`` claims.

Testability. The public-key material is resolved through an injectable
:class:`JWKSClient` protocol (``app.state.jwks_client``), so tests can supply a
locally-generated RSA keypair and exercise the whole dependency offline — no
network and no real Clerk tenant required.
"""

from __future__ import annotations

from typing import Annotated, Any, Protocol, runtime_checkable

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError, PyJWK, PyJWKClient
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from wishly.api import config
from wishly.api.errors import unauthorized
from wishly.db.session import get_session

# Clerk session tokens are signed with RS256.
_ALGORITHMS = ["RS256"]

# ``auto_error=False`` so a *missing* credential yields our own 401 (with a
# ``WWW-Authenticate`` header) rather than FastAPI's default 403.
_bearer_scheme = HTTPBearer(auto_error=False)


class AuthedUser(BaseModel):
    """Identity extracted from a verified Clerk session token.

    This is the request-time principal. It is intentionally *not* the DB
    :class:`~wishly.db.models.User`; provisioning a row from these claims is the
    job of the ``/me`` route.
    """

    sub: str
    email: str
    first_name: str | None = None
    last_name: str | None = None


@runtime_checkable
class JWKSClient(Protocol):
    """Minimal signing-key resolver, satisfied by :class:`jwt.PyJWKClient`.

    Abstracting this is what makes the dependency testable offline: a test can
    install a fake that returns a locally-generated public key.
    """

    def get_signing_key_from_jwt(self, token: str) -> PyJWK: ...


class _BypassJWKSClient:
    """Placeholder key resolver for the dev auth bypass (never invoked).

    When :func:`wishly.api.config.dev_auth_bypass` is on, tokens are not
    verified, so this satisfies the dependency without a configured JWKS source.
    """

    def get_signing_key_from_jwt(self, token: str) -> PyJWK:  # pragma: no cover - never called
        raise RuntimeError("JWKS resolution is disabled under the dev auth bypass.")


def get_jwks_client(request: Request) -> JWKSClient:
    """Return the JWKS client, preferring an override on ``app.state``.

    Production uses a lazily-created, caching :class:`jwt.PyJWKClient` pointed at
    Clerk's JWKS endpoint. Tests set ``app.state.jwks_client`` to a fake.
    """
    override: JWKSClient | None = getattr(request.app.state, "jwks_client", None)
    if override is not None:
        return override

    # Dev bypass: no real Clerk tenant, nothing to verify against.
    if config.dev_auth_bypass():
        return _BypassJWKSClient()

    jwks_url = config.clerk_jwks_url()
    if not jwks_url:
        # Without a configured JWKS source and no override there is nothing to
        # verify against; treat as an auth failure rather than crashing.
        raise unauthorized("Token verification is not configured.")

    client = PyJWKClient(jwks_url, cache_keys=True)
    # Cache on app.state so we build one client per process.
    request.app.state.jwks_client = client
    return client


def _decode_claims(token: str, jwks_client: JWKSClient) -> dict[str, Any]:
    """Verify ``token`` and return its claims, or raise our 401."""
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
    except Exception as exc:  # noqa: BLE001 — any JWKS lookup failure is an auth failure
        # Network errors, unknown ``kid``, or a malformed header all mean the
        # caller cannot be authenticated.
        raise unauthorized("Could not resolve a signing key for the token.") from exc

    issuer = config.clerk_issuer()
    try:
        # ``require`` enforces presence; ``verify_iss`` is only on when an issuer
        # is configured. Passed as a literal so mypy validates it against PyJWT's
        # ``Options`` TypedDict.
        claims: dict[str, Any] = jwt.decode(
            token,
            signing_key.key,
            algorithms=_ALGORITHMS,
            issuer=issuer,
            options={"require": ["exp", "sub"], "verify_iss": issuer is not None},
        )
    except InvalidTokenError as exc:
        raise unauthorized(f"Invalid token: {exc}") from exc
    return claims


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    jwks_client: Annotated[JWKSClient, Depends(get_jwks_client)],
) -> AuthedUser:
    """FastAPI dependency: verify the Bearer token and return the principal.

    Raises ``401 Unauthorized`` for missing, malformed, expired, or
    badly-signed tokens, or when required claims are absent.
    """
    # Dev bypass (non-prod only): authenticate a fixed local user so the UI can
    # run against a real backend without Clerk. See ``config.dev_auth_bypass``.
    if config.dev_auth_bypass():
        return AuthedUser(
            sub=config.DEV_USER_SUB,
            email=config.DEV_USER_EMAIL,
            first_name=config.DEV_USER_FIRST_NAME,
            last_name=config.DEV_USER_LAST_NAME,
        )

    if credentials is None or not credentials.credentials:
        raise unauthorized("Missing bearer token.")

    claims = _decode_claims(credentials.credentials, jwks_client)

    try:
        return AuthedUser(
            sub=claims["sub"],
            email=claims["email"],
            first_name=claims.get("first_name"),
            last_name=claims.get("last_name"),
        )
    except (KeyError, ValidationError) as exc:
        # ``sub`` is guaranteed by the decode ``require``; a missing ``email``
        # means the Clerk session-token claim (PLAN §10) is not configured.
        raise unauthorized("Token is missing required identity claims.") from exc


# Public dependency aliases used by routes.
CurrentUser = Annotated[AuthedUser, Depends(get_current_user)]
DBSession = Annotated[AsyncSession, Depends(get_session)]
