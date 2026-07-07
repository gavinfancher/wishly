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
