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

Transport. The JWKS fetch is the only outbound HTTP call the API makes itself,
and it goes over :mod:`httpx` like everything else in the project —
:class:`HttpxJWKClient` swaps PyJWT's ``urllib``-based fetch for an httpx one
while keeping PyJWT's two-tier key caching.

Testability. The public-key material is resolved through an injectable
:class:`JWKSClient` protocol (``app.state.jwks_client``), so tests can supply a
locally-generated RSA keypair and exercise the whole dependency offline — no
network and no real Clerk tenant required.
"""

from __future__ import annotations

import json
from typing import Annotated, Any, Protocol, runtime_checkable

import httpx
import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError, PyJWK, PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError
from pydantic import BaseModel, ValidationError
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from wishly.api.errors import unauthorized
from wishly.core.logging import get_logger
from wishly.core.settings import (
    settings,
)
from wishly.db.models import User
from wishly.db.session import get_session

logger = get_logger("wishly.api.deps")

# Clerk session tokens are signed with RS256.
_ALGORITHMS = ["RS256"]

# ``auto_error=False`` so a *missing* credential yields our own 401 (with a
# ``WWW-Authenticate`` header) rather than FastAPI's default 403.
_bearer_scheme = HTTPBearer(auto_error=False)

# Clerk's JWKS endpoint is small and close; a token that cannot be verified
# quickly is better rejected than left holding a worker thread.
JWKS_TIMEOUT_SECONDS = 5.0


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


class HttpxJWKClient(PyJWKClient):
    """:class:`jwt.PyJWKClient` that fetches the JWK Set with ``httpx``.

    PyJWT ships a ``urllib.request``-based fetch. Only that one method is
    replaced, so the caching (JWK Set TTL + per-``kid`` LRU) and key parsing
    still come from PyJWT; the URI scheme is validated by ``PyJWKClient``'s own
    constructor before we ever issue a request.
    """

    def fetch_data(self) -> Any:
        try:
            response = httpx.get(
                self.uri,
                headers=self.headers,
                timeout=self.timeout,
                follow_redirects=True,
            )
            response.raise_for_status()
            jwk_set = response.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            # Same exception type PyJWT raises, so callers (and the 401 mapping
            # in ``_decode_claims``) do not have to care which transport ran.
            raise PyJWKClientConnectionError(
                f'Fail to fetch data from the url, err: "{exc}"'
            ) from exc

        # Mirrors PyJWT: only a *successful* fetch refreshes the cache, so a
        # transient outage does not wipe a good JWK Set.
        if self.jwk_set_cache is not None:
            self.jwk_set_cache.put(jwk_set)
        return jwk_set


def get_jwks_client(request: Request) -> JWKSClient:
    """Return the JWKS client, preferring an override on ``app.state``.

    Production uses a lazily-created, caching :class:`HttpxJWKClient` pointed at
    Clerk's JWKS endpoint. Tests set ``app.state.jwks_client`` to a fake.
    """
    override: JWKSClient | None = getattr(request.app.state, "jwks_client", None)
    if override is not None:
        return override

    jwks_url = settings.jwks_url
    if not jwks_url:
        # Without a configured JWKS source and no override there is nothing to
        # verify against; treat as an auth failure rather than crashing.
        raise unauthorized("Token verification is not configured.")

    client = HttpxJWKClient(jwks_url, cache_keys=True, timeout=JWKS_TIMEOUT_SECONDS)
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

    issuer = settings.clerk_issuer
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

    Every request is verified against Clerk. There is no bypass: a flag that
    authenticates an arbitrary caller is one environment variable away from
    doing it in production, so it does not exist.

    Raises ``401 Unauthorized`` for missing, malformed, expired, or
    badly-signed tokens, or when required claims are absent.
    """
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


async def provision_user(session: AsyncSession, principal: AuthedUser) -> User:
    """Insert-or-fetch the ``users`` row for a verified principal.

    Provision-on-first-request: on a user's first authenticated call we create
    their row from the JWT claims. Uses an idempotent ``on conflict do nothing``
    so a racing request (or a Clerk webhook that arrived first) does not error;
    we then read the row back.

    Never commits — that is owned by the ``get_session`` dependency.
    """
    stmt = (
        pg_insert(User)
        .values(
            id=principal.sub,
            email=principal.email,
            first_name=principal.first_name,
            last_name=principal.last_name,
        )
        .on_conflict_do_nothing(index_elements=[User.id])
        .returning(User.id)
    )
    inserted = (await session.execute(stmt)).scalar_one_or_none()
    await session.flush()
    user = await session.get(User, principal.sub)
    assert user is not None  # the insert (or a prior row) guarantees existence

    # ``inserted`` is non-None only when the insert actually created the row. A
    # *new* row for a user who has signed in before means their previous row
    # disappeared — which also silently resets onboarded_at and cascades away
    # their events. Logged loudly because nothing in this app deletes a user.
    if inserted is not None:
        logger.warning(
            "user row provisioned (new)",
            extra={"user_id": principal.sub, "created_at": str(user.created_at)},
        )
    return user


# Public dependency aliases used by routes.
CurrentUser = Annotated[AuthedUser, Depends(get_current_user)]
DBSession = Annotated[AsyncSession, Depends(get_session)]
