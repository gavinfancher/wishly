"""Who is calling? Email + password sessions for users, a shared token for the
hourly run.

How a session works:
  1. Sign up or log in → we create a random token, store its SHA-256 in
     `sessions`, and return the token itself. It's shown once, never stored.
  2. The browser sends it back on every request: `Authorization: Bearer <token>`.
  3. We hash what arrives and look the hash up. Found and not expired = signed in.
  4. Log out deletes the row, so the token stops working immediately.
"""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from psycopg import Connection
from psycopg.errors import UniqueViolation
from pydantic import BaseModel, Field, field_validator

from wishly.db import get_conn
from wishly.passwords import DUMMY_HASH, hash_password, verify_password

SESSION_LENGTH = timedelta(days=30)

router = APIRouter(prefix="/v1/auth", tags=["auth"])
bearer = HTTPBearer()
Token = Annotated[HTTPAuthorizationCredentials, Depends(bearer)]
Conn = Annotated[Connection, Depends(get_conn)]


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# --- request and response bodies ---------------------------------------------------


class Credentials(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=12, max_length=200)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value:
            raise ValueError("not an email address")
        return value


class User(BaseModel):
    id: int
    email: str
    timezone: str
    send_hour: int
    onboarded_at: datetime | None
    created_at: datetime


class SessionOut(BaseModel):
    token: str
    user: User


def start_session(conn: Connection, user: dict[str, Any]) -> SessionOut:
    token = secrets.token_urlsafe(32)  # 256 random bits
    conn.execute(
        "insert into sessions (token_hash, user_id, expires_at) values (%s, %s, %s)",
        (hash_token(token), user["id"], datetime.now(UTC) + SESSION_LENGTH),
    )
    return SessionOut(token=token, user=User(**user))


# --- routes ------------------------------------------------------------------------


@router.post("/signup", status_code=201)
def signup(body: Credentials, request: Request, conn: Conn) -> SessionOut:
    if not request.app.state.settings.signup_enabled:
        raise HTTPException(status_code=403, detail="sign-ups are closed")
    try:
        user = conn.execute(
            "insert into users (email, password_hash) values (%s, %s) returning *",
            (body.email, hash_password(body.password)),
        ).fetchone()
    except UniqueViolation as exc:
        raise HTTPException(status_code=409, detail="that email already has an account") from exc
    return start_session(conn, user)


@router.post("/login")
def login(body: Credentials, conn: Conn) -> SessionOut:
    user = conn.execute("select * from users where email = %s", (body.email,)).fetchone()
    # Always run the slow hash, even for an unknown email, and give one message
    # for both cases: nothing reveals which emails have accounts.
    password_ok = verify_password(body.password, user["password_hash"] if user else DUMMY_HASH)
    if user is None or not password_ok:
        raise HTTPException(status_code=401, detail="invalid email or password")
    return start_session(conn, user)


@router.post("/logout", status_code=204)
def logout(token: Token, conn: Conn) -> Response:
    conn.execute("delete from sessions where token_hash = %s", (hash_token(token.credentials),))
    return Response(status_code=204)


# --- dependencies other routes use -------------------------------------------------


def current_user(token: Token, conn: Conn) -> dict[str, Any]:
    """The signed-in user, or 401."""
    user = conn.execute(
        """
        select u.* from sessions s join users u on u.id = s.user_id
        where s.token_hash = %s and s.expires_at > now()
        """,
        (hash_token(token.credentials),),
    ).fetchone()
    if user is None:
        raise HTTPException(status_code=401, detail="not signed in")
    return user


def require_run_token(request: Request, token: Token) -> None:
    expected = request.app.state.settings.run_token.get_secret_value()
    # compare_digest takes the same time whether the first or last character
    # differs, so response timing can't be used to guess the token.
    if not hmac.compare_digest(token.credentials, expected):
        raise HTTPException(status_code=401, detail="invalid run token")


CurrentUser = Annotated[dict[str, Any], Depends(current_user)]
