"""Tests for :mod:`wishly.core.settings`."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from wishly.core.settings import Settings


def test_settings_reads_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://wishly:wishly@localhost:5432/wishly")
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://wishly.dev, https://www.wishly.dev")
    s = Settings(_env_file=None)  # type: ignore[call-arg]

    assert s.environment == "prod"
    assert s.is_prod is True
    assert s.allowed_origins == ["https://wishly.dev", "https://www.wishly.dev"]


def test_async_and_sync_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://wishly:wishly@localhost:5432/wishly")
    s = Settings(_env_file=None)  # type: ignore[call-arg]

    assert s.async_database_url.startswith("postgresql+asyncpg://")
    assert s.sync_database_url.startswith("postgresql+psycopg://")
    # The credentials/host/db portion is preserved.
    assert s.async_database_url.endswith("wishly:wishly@localhost:5432/wishly")


def test_missing_database_url_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


class TestSslParamTranslation:
    """The two drivers disagree about how to ask for TLS, and neither tolerates
    the other's spelling. Verified against real drivers: psycopg rejects `ssl`
    with `invalid connection option "ssl"`, and asyncpg rejects `sslmode` with
    `TypeError: connect() got an unexpected keyword argument 'sslmode'` — at
    connect time, so it breaks every request rather than failing at startup.

    `sslmode` is the canonical spelling in DATABASE_URL; settings renames it.
    """

    @staticmethod
    def _settings(dsn: str) -> Settings:
        return Settings(_env_file=None, database_url=dsn)  # type: ignore[call-arg]

    def test_sslmode_becomes_ssl_for_asyncpg(self) -> None:
        s = self._settings("postgresql://u:p@rds.example.com:5432/wishly?sslmode=require")
        assert s.async_database_url.endswith("/wishly?ssl=require")
        assert "sslmode" not in s.async_database_url

    def test_sslmode_is_preserved_for_psycopg(self) -> None:
        s = self._settings("postgresql://u:p@rds.example.com:5432/wishly?sslmode=require")
        assert s.sync_database_url.endswith("/wishly?sslmode=require")
        assert "ssl=" not in s.sync_database_url.replace("sslmode=", "")

    def test_ssl_spelling_is_also_normalised(self) -> None:
        """Accept `ssl=` in the env too, rather than silently passing it to psycopg."""
        s = self._settings("postgresql://u:p@rds.example.com:5432/wishly?ssl=verify-full")
        assert s.sync_database_url.endswith("?sslmode=verify-full")
        assert s.async_database_url.endswith("?ssl=verify-full")

    def test_other_query_params_survive(self) -> None:
        s = self._settings(
            "postgresql://u:p@rds.example.com:5432/wishly?sslmode=require&application_name=wishly"
        )
        for url in (s.sync_database_url, s.async_database_url):
            assert "application_name=wishly" in url

    def test_no_query_string_is_left_alone(self) -> None:
        s = self._settings("postgresql://u:p@localhost:5432/wishly")
        assert s.sync_database_url == "postgresql+psycopg://u:p@localhost:5432/wishly"
        assert s.async_database_url == "postgresql+asyncpg://u:p@localhost:5432/wishly"
        assert "?" not in s.async_database_url
