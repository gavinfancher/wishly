from datetime import UTC, datetime, timedelta

import psycopg
from fastapi.testclient import TestClient

from tests.conftest import PING_TOKEN, make_settings
from wishly.main import create_app
from wishly.ping import PINGS_PER_MINUTE

KEY = {"Authorization": f"Bearer {PING_TOKEN}"}


def test_ping_needs_the_key(anonymous: TestClient) -> None:
    assert anonymous.get("/internal/ping").status_code in (401, 403)
    wrong = {"Authorization": "Bearer wrong"}
    assert anonymous.get("/internal/ping", headers=wrong).status_code == 401


def test_a_session_token_is_not_the_ping_key(client: TestClient) -> None:
    assert client.get("/internal/ping").status_code == 401


def test_ping_ok_when_database_answers(anonymous: TestClient) -> None:
    response = anonymous.get("/internal/ping", headers=KEY)

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ping_503_when_database_is_down() -> None:
    settings = make_settings(database_url="postgresql://nobody@127.0.0.1:1/nothing")
    with TestClient(create_app(settings)) as client:
        assert client.get("/internal/ping", headers=KEY).status_code == 503


def test_ping_503_when_scheduler_stalled(db: psycopg.Connection) -> None:
    with TestClient(create_app(make_settings(scheduler_enabled=True))) as client:
        scheduler = client.app.state.scheduler
        scheduler.started_at = datetime.now(UTC) - timedelta(hours=1)  # no tick since

        response = client.get("/internal/ping", headers=KEY)

    assert response.status_code == 503
    assert response.json()["detail"] == "scheduler stalled"


def test_ping_is_rate_limited_per_client_before_the_key_is_checked(
    anonymous: TestClient,
) -> None:
    attacker = {"CF-Connecting-IP": "203.0.113.9", "Authorization": "Bearer guess"}
    for _ in range(PINGS_PER_MINUTE):
        assert anonymous.get("/internal/ping", headers=attacker).status_code == 401
    assert anonymous.get("/internal/ping", headers=attacker).status_code == 429

    # Someone else (the watchdog) is unaffected.
    watchdog = KEY | {"CF-Connecting-IP": "198.51.100.1"}
    assert anonymous.get("/internal/ping", headers=watchdog).status_code == 200
