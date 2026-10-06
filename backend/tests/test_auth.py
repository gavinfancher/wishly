"""Real token verification, with our own RSA key standing in for Clerk's."""

import time
from collections.abc import Iterator
from types import SimpleNamespace

import jwt
import psycopg
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from tests.conftest import make_settings
from wishly import auth
from wishly.main import create_app

ISSUER = make_settings().clerk_issuer
CLERK_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
ATTACKER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def client(db: psycopg.Connection, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    # Instead of fetching Clerk's public key over the network, hand back ours.
    fake_jwks = SimpleNamespace(
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key=CLERK_KEY.public_key())
    )
    monkeypatch.setattr(auth, "jwks_client", lambda issuer: fake_jwks)
    with TestClient(create_app(make_settings())) as client:
        yield client


def token(*, key: rsa.RSAPrivateKey = CLERK_KEY, **claims: object) -> dict[str, str]:
    payload = {
        "sub": "user_a",
        "email": "a@example.com",
        "iss": ISSUER,
        "exp": int(time.time()) + 60,
    } | claims
    return {"Authorization": f"Bearer {jwt.encode(payload, key, algorithm='RS256')}"}


def test_valid_token_is_accepted(client: TestClient) -> None:
    response = client.get("/v1/me", headers=token())

    assert response.status_code == 200
    assert response.json()["id"] == "user_a"


@pytest.mark.parametrize(
    "headers",
    [
        pytest.param({}, id="no token"),
        pytest.param({"Authorization": "Bearer not-a-jwt"}, id="garbage"),
        pytest.param(token(exp=int(time.time()) - 1), id="expired"),
        pytest.param(token(iss="https://evil.example"), id="wrong issuer"),
        pytest.param(token(key=ATTACKER_KEY), id="signed by someone else"),
    ],
)
def test_bad_tokens_are_rejected(client: TestClient, headers: dict[str, str]) -> None:
    assert client.get("/v1/me", headers=headers).status_code == 401
