"""Auth dependency (T2.1) and /me provisioning + preferences (T2.2)."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.api.conftest import auth_headers
from wishly.db.models import User


# --- Auth 401s ------------------------------------------------------------- #
async def test_missing_token_returns_401(client: AsyncClient) -> None:
    resp = await client.get("/me")
    assert resp.status_code == 401
    assert resp.headers.get("www-authenticate") == "Bearer"


async def test_malformed_token_returns_401(client: AsyncClient) -> None:
    resp = await client.get("/me", headers=auth_headers("not-a-jwt"))
    assert resp.status_code == 401


async def test_expired_token_returns_401(
    client: AsyncClient, make_token: Callable[..., str]
) -> None:
    resp = await client.get("/me", headers=auth_headers(make_token(expired=True)))
    assert resp.status_code == 401


async def test_token_signed_by_wrong_key_returns_401(
    client: AsyncClient, make_token: Callable[..., str]
) -> None:
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    bad = make_token(sub="user_1", sign_with=other_key)
    resp = await client.get("/me", headers=auth_headers(bad))
    assert resp.status_code == 401


async def test_token_missing_email_claim_returns_401(
    client: AsyncClient, make_token: Callable[..., str]
) -> None:
    # PLAN §10 custom claim absent → identity incomplete → 401.
    resp = await client.get("/me", headers=auth_headers(make_token(email=None)))
    assert resp.status_code == 401


# --- /me provisioning ------------------------------------------------------ #
async def test_get_me_provisions_user_on_first_request(
    client: AsyncClient, make_token: Callable[..., str], db: AsyncSession
) -> None:
    token = make_token(sub="user_prov", email="prov@example.com", first_name="Pro", last_name="V")
    resp = await client.get("/me", headers=auth_headers(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "user_prov"
    assert body["email"] == "prov@example.com"
    assert body["first_name"] == "Pro"
    assert body["timezone"] == "UTC"
    assert body["send_hour"] == 8

    # The row now exists in Postgres.
    user = await db.get(User, "user_prov")
    assert user is not None
    assert user.email == "prov@example.com"


async def test_get_me_is_idempotent(
    client: AsyncClient, make_token: Callable[..., str], db: AsyncSession
) -> None:
    token = make_token(sub="user_idem", email="idem@example.com")
    await client.get("/me", headers=auth_headers(token))
    await client.get("/me", headers=auth_headers(token))
    rows = (await db.execute(select(User).where(User.id == "user_idem"))).scalars().all()
    assert len(rows) == 1


# --- PATCH /me ------------------------------------------------------------- #
async def test_patch_me_updates_preferences(
    client: AsyncClient, make_token: Callable[..., str]
) -> None:
    token = make_token(sub="user_pref", email="pref@example.com")
    resp = await client.patch(
        "/me",
        headers=auth_headers(token),
        json={"timezone": "America/New_York", "send_hour": 6},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["timezone"] == "America/New_York"
    assert body["send_hour"] == 6


async def test_patch_me_rejects_invalid_timezone(
    client: AsyncClient, make_token: Callable[..., str]
) -> None:
    token = make_token(sub="user_tz", email="tz@example.com")
    resp = await client.patch("/me", headers=auth_headers(token), json={"timezone": "Mars/Phobos"})
    assert resp.status_code == 422


@pytest.mark.parametrize("hour", [-1, 24, 99])
async def test_patch_me_rejects_invalid_send_hour(
    client: AsyncClient, make_token: Callable[..., str], hour: int
) -> None:
    token = make_token(sub="user_hr", email="hr@example.com")
    resp = await client.patch("/me", headers=auth_headers(token), json={"send_hour": hour})
    assert resp.status_code == 422


async def test_patch_me_requires_a_field(
    client: AsyncClient, make_token: Callable[..., str]
) -> None:
    token = make_token(sub="user_empty", email="empty@example.com")
    resp = await client.patch("/me", headers=auth_headers(token), json={})
    assert resp.status_code == 422
