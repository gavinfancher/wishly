from fastapi.testclient import TestClient

from wishly.main import create_app
from wishly.settings import Settings


def test_healthz_reports_ok_and_version() -> None:
    client = TestClient(create_app(Settings(env="test", version="abc123")))

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "abc123"}


def test_docs_hidden_in_prod() -> None:
    client = TestClient(create_app(Settings(env="prod")))

    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404
