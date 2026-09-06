"""Fixtures for the API test suite.

Design goals:

* **Offline auth.** A module-level RSA keypair signs test JWTs; a fake JWKS
  client (installed on ``app.state.jwks_client``) returns the matching public
  key. The real :mod:`wishly.api.deps` verification path runs unchanged — no
  network, no Clerk tenant.
* **Real Postgres.** Integration tests run against the ``wishly_test`` database,
  whose schema the root ``conftest.py`` builds from ``infra/sql/schema.sql``.
  Each test starts from clean tables (``TRUNCATE`` in :func:`_clean_tables`).
* **Webhook signing.** Real :class:`svix.webhooks.Webhook` secrets are installed
  on ``app.state`` so the production Svix verification path is exercised; helper
  factories build correctly-signed payloads.
"""

from __future__ import annotations

import base64
import json
import os
import uuid
from collections.abc import AsyncIterator, Callable, Iterator
from typing import Any

import jwt
import pendulum
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport, AsyncClient
from jwt import PyJWK, algorithms
from svix.webhooks import Webhook

# Ensure settings can instantiate before importing app modules.
os.environ.setdefault("DATABASE_URL", "postgresql://wishly:wishly@localhost:5432/wishly_test")

os.environ.setdefault("ENVIRONMENT", "dev")


# SAFETY INTERLOCK. These fixtures TRUNCATE every table, so they must never point
# at a real database. A previous configuration defaulted to the development
# database and silently wiped live data on every test run; refusing to start is
# the only reliable prevention, because the damage is invisible until someone
# notices their rows are gone.
_dsn = os.environ["DATABASE_URL"]
if not _dsn.rsplit("/", 1)[-1].split("?")[0].endswith("_test"):
    raise RuntimeError(
        f"Refusing to run: DATABASE_URL must name a database ending in '_test', got {_dsn!r}. "
        "These tests truncate every table."
    )


from fastapi import FastAPI  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from wishly.api.deps import get_jwks_client  # noqa: E402
from wishly.api.main import create_app  # noqa: E402
from wishly.api.webhooks import clerk as clerk_webhook  # noqa: E402
from wishly.api.webhooks import resend as resend_webhook  # noqa: E402
from wishly.api.webhooks.verify import SvixVerifier  # noqa: E402
from wishly.core.settings import settings  # noqa: E402
from wishly.db.session import get_session  # noqa: E402

# Tables truncated between tests (children before parents not required with
# CASCADE, but listed for clarity).
_TABLES = (
    "notification_log",
    "event_reminders",
    "events",
    "templates",
    "suppressions",
    "users",
)

# A signing secret shared by both webhook fixtures (any valid Svix secret).
_WEBHOOK_SECRET = "whsec_" + base64.b64encode(b"0123456789abcdef0123456789abcdef").decode()
_TEST_KID = "test-key"


# --------------------------------------------------------------------------- #
# Auth: RSA keypair + token factory + fake JWKS client
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="session")
def rsa_key() -> rsa.RSAPrivateKey:
    """A session-wide RSA private key used to sign test JWTs."""
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="session")
def public_jwk(rsa_key: rsa.RSAPrivateKey) -> PyJWK:
    """The public half of :func:`rsa_key`, as a :class:`jwt.PyJWK`."""
    jwk_dict = json.loads(algorithms.RSAAlgorithm.to_jwk(rsa_key.public_key()))
    jwk_dict["kid"] = _TEST_KID
    return PyJWK.from_dict(jwk_dict)


class _FakeJWKSClient:
    """Offline stand-in for :class:`jwt.PyJWKClient`."""

    def __init__(self, jwk: PyJWK) -> None:
        self._jwk = jwk

    def get_signing_key_from_jwt(self, token: str) -> PyJWK:  # noqa: ARG002
        return self._jwk


@pytest.fixture
def make_token(rsa_key: rsa.RSAPrivateKey) -> Callable[..., str]:
    """Return a factory that mints signed Clerk-style session tokens.

    Usage::

        token = make_token(sub="user_1", email="a@b.com", first_name="A")
        token = make_token(sub="user_1", expired=True)
    """

    def _make(
        *,
        sub: str = "user_test",
        email: str | None = "user@example.com",
        first_name: str | None = "Test",
        last_name: str | None = "User",
        expired: bool = False,
        extra_claims: dict[str, Any] | None = None,
        sign_with: rsa.RSAPrivateKey | None = None,
    ) -> str:
        now = pendulum.now("UTC")
        exp = now.subtract(minutes=5) if expired else now.add(hours=1)
        claims: dict[str, Any] = {
            "sub": sub,
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
        }
        if email is not None:
            claims["email"] = email
        if first_name is not None:
            claims["first_name"] = first_name
        if last_name is not None:
            claims["last_name"] = last_name
        if extra_claims:
            claims.update(extra_claims)
        key = sign_with if sign_with is not None else rsa_key
        return jwt.encode(claims, key, algorithm="RS256", headers={"kid": _TEST_KID})

    return _make


# --------------------------------------------------------------------------- #
# Database: live Postgres, clean tables per test
# --------------------------------------------------------------------------- #
@pytest_asyncio.fixture
async def _clean_tables() -> AsyncIterator[None]:
    """Truncate all app tables before (and after) each test for isolation."""
    engine = create_async_engine(settings.async_database_url)
    async with engine.begin() as conn:
        await conn.execute(text(f"truncate {', '.join(_TABLES)} restart identity cascade"))
    try:
        yield
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """A test-scoped async sessionmaker bound to a dedicated engine."""
    engine = create_async_engine(settings.async_database_url)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def db(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """A standalone session for arranging/asserting DB state inside a test."""
    async with session_factory() as session:
        yield session


# --------------------------------------------------------------------------- #
# App + HTTP client with all dependencies overridden for offline operation
# --------------------------------------------------------------------------- #
@pytest.fixture
def app(
    public_jwk: PyJWK,
    session_factory: async_sessionmaker[AsyncSession],
) -> FastAPI:
    """A FastAPI app wired for offline tests.

    * ``get_jwks_client`` → fake JWKS client (our RSA public key).
    * ``get_session`` → test session factory (commits within the request).
    * Webhook verifiers → real Svix verifier with the test secret.
    """
    application = create_app()
    application.state.jwks_client = _FakeJWKSClient(public_jwk)

    fake_jwks = _FakeJWKSClient(public_jwk)
    application.dependency_overrides[get_jwks_client] = lambda: fake_jwks

    async def _override_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    application.dependency_overrides[get_session] = _override_session

    verifier = SvixVerifier(_WEBHOOK_SECRET)
    setattr(application.state, clerk_webhook.VERIFIER_STATE_ATTR, verifier)
    setattr(application.state, resend_webhook.VERIFIER_STATE_ATTR, verifier)

    return application


@pytest_asyncio.fixture
async def client(app: FastAPI, _clean_tables: None) -> AsyncIterator[AsyncClient]:
    """An ``httpx`` client bound to the test app over ASGI (no network)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


def auth_headers(token: str) -> dict[str, str]:
    """Build an ``Authorization: Bearer`` header dict."""
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------------- #
# Webhook payload signing helpers
# --------------------------------------------------------------------------- #
@pytest.fixture
def webhook_secret() -> str:
    """The Svix signing secret the test app verifies against."""
    return _WEBHOOK_SECRET


@pytest.fixture
def sign_webhook() -> Callable[[dict[str, Any]], tuple[bytes, dict[str, str]]]:
    """Return a factory that produces ``(body, headers)`` correctly Svix-signed."""
    wh = Webhook(_WEBHOOK_SECRET)

    def _sign(payload: dict[str, Any]) -> tuple[bytes, dict[str, str]]:
        body = json.dumps(payload).encode()
        msg_id = f"msg_{uuid.uuid4().hex}"
        ts = pendulum.now("UTC")
        signature = wh.sign(msg_id, ts, body.decode())
        headers = {
            "svix-id": msg_id,
            "svix-timestamp": str(int(ts.timestamp())),
            "svix-signature": signature,
            "content-type": "application/json",
        }
        return body, headers

    return _sign


@pytest.fixture
def bad_webhook_headers() -> Iterator[Callable[[dict[str, Any]], tuple[bytes, dict[str, str]]]]:
    """A factory that returns a body with an **invalid** signature."""

    def _bad(payload: dict[str, Any]) -> tuple[bytes, dict[str, str]]:
        body = json.dumps(payload).encode()
        headers = {
            "svix-id": "msg_bad",
            "svix-timestamp": str(int(pendulum.now("UTC").timestamp())),
            "svix-signature": "v1,not-a-real-signature",
            "content-type": "application/json",
        }
        return body, headers

    yield _bad
