import psycopg
from fastapi.testclient import TestClient

from tests.conftest import make_settings
from wishly.main import create_app

# Nothing listens on port 1, so connections to it are refused.
UNREACHABLE_DB = "postgresql://nobody@127.0.0.1:1/nothing"


def test_healthz_reports_ok_and_version() -> None:
    client = TestClient(create_app(make_settings(database_url=UNREACHABLE_DB, version="abc123")))

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "abc123"}


def test_docs_hidden_in_prod() -> None:
    client = TestClient(create_app(make_settings(database_url=UNREACHABLE_DB, env="prod")))

    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_healthy_but_not_ready_when_database_is_down() -> None:
    # `with` runs startup/shutdown, so the pool is opened (and fails to connect).
    with TestClient(create_app(make_settings(database_url=UNREACHABLE_DB))) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/readyz").status_code == 503


def test_ready_when_database_is_up(db: psycopg.Connection) -> None:
    with TestClient(create_app(make_settings())) as client:
        response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
