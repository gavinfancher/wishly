import psycopg
import pytest
from fastapi.testclient import TestClient

from tests.conftest import PASSWORD, make_settings, sign_up
from wishly.main import create_app
from wishly.passwords import hash_password, verify_password


def login(client: TestClient, email: str, password: str = PASSWORD):
    return client.post("/v1/auth/login", json={"email": email, "password": password})


def test_signup_returns_a_working_session(anonymous: TestClient) -> None:
    headers = sign_up(anonymous, "a@example.com")

    me = anonymous.get("/v1/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "a@example.com"


def test_email_is_case_insensitive(anonymous: TestClient) -> None:
    sign_up(anonymous, "Me@Example.com")

    assert login(anonymous, "  me@example.COM ").status_code == 200
    duplicate = anonymous.post(
        "/v1/auth/signup", json={"email": "ME@example.com", "password": PASSWORD}
    )
    assert duplicate.status_code == 409


def test_short_password_is_rejected(anonymous: TestClient) -> None:
    response = anonymous.post("/v1/auth/signup", json={"email": "a@b.co", "password": "short"})
    assert response.status_code == 422


def test_wrong_password_and_unknown_email_look_the_same(anonymous: TestClient) -> None:
    sign_up(anonymous, "a@example.com")

    wrong_password = login(anonymous, "a@example.com", "not the right password")
    unknown_email = login(anonymous, "nobody@example.com")

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


def test_logout_kills_the_token(anonymous: TestClient) -> None:
    headers = sign_up(anonymous, "a@example.com")

    assert anonymous.post("/v1/auth/logout", headers=headers).status_code == 204
    assert anonymous.get("/v1/me", headers=headers).status_code == 401


def test_expired_session_is_rejected(anonymous: TestClient, db: psycopg.Connection) -> None:
    headers = sign_up(anonymous, "a@example.com")
    db.execute("update sessions set expires_at = now() - interval '1 second'")

    assert anonymous.get("/v1/me", headers=headers).status_code == 401


def test_only_the_token_hash_is_stored(anonymous: TestClient, db: psycopg.Connection) -> None:
    token = sign_up(anonymous, "a@example.com")["Authorization"].removeprefix("Bearer ")

    stored = db.execute("select token_hash from sessions").fetchone()["token_hash"]
    assert stored != token
    assert len(stored) == 64  # hex SHA-256


@pytest.mark.parametrize(
    "headers",
    [
        pytest.param({}, id="no token"),
        pytest.param({"Authorization": "Bearer made-up"}, id="unknown token"),
    ],
)
def test_requests_without_a_valid_session_are_rejected(
    anonymous: TestClient, headers: dict[str, str]
) -> None:
    assert anonymous.get("/v1/me", headers=headers).status_code == 401


def test_signup_can_be_turned_off(db: psycopg.Connection) -> None:
    with TestClient(create_app(make_settings(signup_enabled=False))) as client:
        response = client.post("/v1/auth/signup", json={"email": "a@b.co", "password": PASSWORD})
    assert response.status_code == 403


def test_password_hashes_are_salted() -> None:
    first, second = hash_password(PASSWORD), hash_password(PASSWORD)

    assert first != second  # same password, different salt
    assert verify_password(PASSWORD, first)
    assert not verify_password("something else entirely", first)
