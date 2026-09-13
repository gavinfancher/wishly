"""Tests for :mod:`wishly.core.settings`."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from wishly.core.settings import Settings


def test_settings_reads_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://wishly:wishly@localhost:5432/wishly")
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://wishly.dev, https://www.wishly.dev")
    # Required at ENVIRONMENT=prod: the validator refuses to build Settings
    # without them, which is the point of it.
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_x")
    monkeypatch.setenv("RESEND_API_KEY", "re_x")
    monkeypatch.setenv("TRIGGER_TOKEN", "trg_x")
    s = Settings(_env_file=None)  # type: ignore[call-arg]

    assert s.environment == "prod"
    assert s.is_prod is True
    assert s.allowed_origins == ["https://wishly.dev", "https://www.wishly.dev"]


def test_prod_requires_the_trigger_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without it the hourly send cannot be triggered at all.

    Every /internal route rejects an absent token, so a prod API missing this
    serves browser traffic perfectly, passes /health and /ready, and quietly
    never sends another reminder. Startup is the only place that can notice.
    """
    monkeypatch.setenv("DATABASE_URL", "postgresql://wishly:wishly@localhost:5432/wishly")
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://wishly.dev")
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_x")
    monkeypatch.setenv("RESEND_API_KEY", "re_x")
    monkeypatch.delenv("TRIGGER_TOKEN", raising=False)

    with pytest.raises(ValidationError, match="trigger_token"):
        Settings(_env_file=None)  # type: ignore[call-arg]


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
    """The two drivers disagree about how to ask for TLS.

    psycopg *is* libpq, so it keeps the DSN's parameters verbatim — including
    `sslrootcert=system`, which is how PlanetScale asks for the system trust
    store.

    asyncpg takes none of them. SQLAlchemy's asyncpg dialect turns query
    parameters into `connect()` kwargs, and asyncpg has no `sslrootcert`
    (TypeError at connect time, so every request fails). Even a bare
    `ssl=verify-full` is no good: with no root cert named it goes looking for
    ~/.postgresql/root.crt and ignores SSL_CERT_FILE. So the async URL carries
    no TLS parameters at all and `wishly.db.session` hands asyncpg a real
    SSLContext built from certifi instead.
    """

    @staticmethod
    def _settings(dsn: str) -> Settings:
        return Settings(_env_file=None, database_url=dsn)  # type: ignore[call-arg]

    def test_asyncpg_url_carries_no_tls_params(self) -> None:
        s = self._settings("postgresql://u:p@db.example.com:5432/wishly?sslmode=require")
        assert s.async_database_url.endswith("/wishly")
        for param in ("sslmode", "ssl=", "sslrootcert"):
            assert param not in s.async_database_url

    def test_asyncpg_url_drops_libpq_only_params(self) -> None:
        """The PlanetScale DSN shape. sslrootcert is a TypeError in asyncpg."""
        s = self._settings(
            "postgresql://u:p@db.example.com:5432/wishly?sslmode=verify-full&sslrootcert=system"
        )
        assert "sslrootcert" not in s.async_database_url
        assert s.database_sslmode == "verify-full"

    def test_psycopg_keeps_the_planetscale_dsn_intact(self) -> None:
        s = self._settings(
            "postgresql://u:p@db.example.com:5432/wishly?sslmode=verify-full&sslrootcert=system"
        )
        assert "sslmode=verify-full" in s.sync_database_url
        assert "sslrootcert=system" in s.sync_database_url

    def test_sslmode_is_preserved_for_psycopg(self) -> None:
        s = self._settings("postgresql://u:p@rds.example.com:5432/wishly?sslmode=require")
        assert s.sync_database_url.endswith("/wishly?sslmode=require")
        assert "ssl=" not in s.sync_database_url.replace("sslmode=", "")

    def test_ssl_spelling_is_also_normalised(self) -> None:
        """Accept `ssl=` in the env too, rather than passing it to psycopg."""
        s = self._settings("postgresql://u:p@db.example.com:5432/wishly?ssl=verify-full")
        assert s.sync_database_url.endswith("?sslmode=verify-full")
        assert "ssl" not in s.async_database_url.split("?")[-1]
        assert s.database_sslmode == "verify-full"

    def test_other_query_params_survive(self) -> None:
        s = self._settings(
            "postgresql://u:p@db.example.com:5432/wishly?sslmode=require&application_name=wishly"
        )
        for url in (s.sync_database_url, s.async_database_url):
            assert "application_name=wishly" in url

    def test_no_query_string_is_left_alone(self) -> None:
        s = self._settings("postgresql://u:p@localhost:5432/wishly")
        assert s.sync_database_url == "postgresql+psycopg://u:p@localhost:5432/wishly"
        assert s.async_database_url == "postgresql+asyncpg://u:p@localhost:5432/wishly"
        assert "?" not in s.async_database_url
