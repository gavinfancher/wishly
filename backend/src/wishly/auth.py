"""Who is calling? Clerk session tokens for users, a shared token for EventBridge."""

import hmac
from functools import cache
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from psycopg import Connection

from wishly.db import get_conn

bearer = HTTPBearer()
Token = Annotated[HTTPAuthorizationCredentials, Depends(bearer)]


@cache
def jwks_client(issuer: str) -> jwt.PyJWKClient:
    """Fetches Clerk's public keys once and caches them, so verifying a token
    is local math, not a network call per request."""
    return jwt.PyJWKClient(f"{issuer}/.well-known/jwks.json")


def verified_claims(request: Request, token: Token) -> dict[str, Any]:
    """Check the token was signed by our Clerk instance and hasn't expired."""
    issuer = request.app.state.settings.clerk_issuer
    try:
        key = jwks_client(issuer).get_signing_key_from_jwt(token.credentials)
        return jwt.decode(token.credentials, key.key, algorithms=["RS256"], issuer=issuer)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="invalid session token") from exc


def current_user(
    claims: Annotated[dict[str, Any], Depends(verified_claims)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> dict[str, Any]:
    """The caller's users row, created on their first request.

    The upsert also copies the email from the token every time, so an email
    changed in Clerk shows up here on the user's next visit.
    """
    return conn.execute(
        """
        insert into users (id, email) values (%(id)s, %(email)s)
        on conflict (id) do update set email = excluded.email
        returning *
        """,
        {"id": claims["sub"], "email": claims["email"]},
    ).fetchone()


def require_run_token(request: Request, token: Token) -> None:
    expected = request.app.state.settings.run_token.get_secret_value()
    # compare_digest takes the same time whether the first or last character
    # differs, so response timing can't be used to guess the token.
    if not hmac.compare_digest(token.credentials, expected):
        raise HTTPException(status_code=401, detail="invalid run token")


CurrentUser = Annotated[dict[str, Any], Depends(current_user)]
