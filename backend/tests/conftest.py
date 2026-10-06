"""Shared test fixtures.

Database tests run against the local Postgres from compose.yaml, in its
separate wishly_test database. Start it first:  docker compose up -d
"""

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from wishly.auth import verified_claims
from wishly.main import create_app
from wishly.settings import Settings

TEST_DATABASE_URL = os.environ.get(
    "WISHLY_TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/wishly_test"
)
RUN_TOKEN = "test-run-token"
SCHEMA_SQL = Path(__file__).parents[2] / "infra" / "sql" / "schema.sql"

# The fixtures below drop and empty every table. Refuse to point them at
# anything that isn't obviously a throwaway test database.
if not psycopg.conninfo.conninfo_to_dict(TEST_DATABASE_URL).get("dbname", "").endswith("_test"):
    raise RuntimeError(f"Refusing to run: database name must end in _test: {TEST_DATABASE_URL}")


def make_settings(**overrides: Any) -> Settings:
    values = {
        "env": "test",
        "database_url": TEST_DATABASE_URL,
        "clerk_issuer": "https://clerk.example.test",
        "run_token": RUN_TOKEN,
    }
    return Settings(**(values | overrides))


@pytest.fixture(scope="session")
def database_url() -> str:
    """A test database built from infra/sql/schema.sql. Built once per test run."""
    try:
        conn = psycopg.connect(TEST_DATABASE_URL, autocommit=True, connect_timeout=3)
    except psycopg.OperationalError as exc:
        pytest.fail(f"Test database unreachable — is `docker compose up -d` running?\n{exc}")

    with conn:
        # Start from nothing, so the tests prove schema.sql builds the database.
        conn.execute("drop schema public cascade")
        conn.execute("create schema public")
        conn.execute(SCHEMA_SQL.read_text())
    return TEST_DATABASE_URL


@pytest.fixture
def db(database_url: str) -> Iterator[psycopg.Connection]:
    """A connection for one test. Every table is emptied afterwards."""
    with psycopg.connect(database_url, autocommit=True, row_factory=dict_row) as conn:
        yield conn
        conn.execute("truncate users, reminders, sends cascade")


@pytest.fixture
def emails() -> list[dict[str, str]]:
    """Every email the app 'sent' during a test."""
    return []


@pytest.fixture
def client(db: psycopg.Connection, emails: list) -> Iterator[TestClient]:
    """The app, signed in as user_a. Pass `as_user` headers to switch users."""
    app = create_app(make_settings())
    app.state.send_email = lambda **email: emails.append(email)

    # Skip real Clerk token verification: the Bearer token *is* the user ID.
    def fake_claims(request: Request) -> dict[str, str]:
        user_id = request.headers["Authorization"].removeprefix("Bearer ")
        return {"sub": user_id, "email": f"{user_id}@example.com"}

    app.dependency_overrides[verified_claims] = fake_claims
    with TestClient(app, headers={"Authorization": "Bearer user_a"}) as client:
        yield client


def as_user(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_id}"}
