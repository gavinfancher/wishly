"""Application settings, loaded from environment variables via pydantic-settings.

All configuration is supplied through the environment (never hard-coded). The
canonical list of variables lives in ``docs/PLAN.md`` §11 and the ``.env.example``
files. Required values raise a clear validation error at import/instantiation time
if missing.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

Environment = Literal["dev", "prod"]


class Settings(BaseSettings):
    """Strongly-typed application configuration.

    Reads from process environment and, for local development, from a ``.env``
    file. Field names are case-insensitive against environment variable names.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Database (API uses asyncpg; Dagster/Alembic use sync psycopg) -------
    database_url: str = Field(
        ...,
        description="PostgreSQL DSN, e.g. postgresql://wishly:wishly@localhost:5432/wishly",
    )

    # --- Clerk (auth) --------------------------------------------------------
    clerk_secret_key: str | None = Field(
        default=None, description="Clerk backend secret key / token verification."
    )
    clerk_webhook_signing_secret: str | None = Field(
        default=None, description="Svix signing secret for /webhooks/clerk."
    )

    # --- Resend (email) ------------------------------------------------------
    resend_api_key: str | None = Field(default=None, description="Resend API key.")
    resend_webhook_signing_secret: str | None = Field(
        default=None, description="Signing secret for /webhooks/resend."
    )
    email_from: str = Field(
        default="reminders@wishly.dev",
        description="From address for outbound email (domain must be verified).",
    )

    # --- App / API -----------------------------------------------------------
    app_base_url: str = Field(
        default="http://localhost:5173",
        description="Public base URL of the SPA; used to build manage_url in emails.",
    )
    # ``NoDecode`` stops pydantic-settings from JSON-decoding the raw env value so
    # the validator below can split a plain comma-separated string.
    allowed_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"],
        description="CORS allowlist for the API (comma-separated in the env).",
    )
    environment: Environment = Field(default="dev", description="Deployment environment.")

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Allow ``ALLOWED_ORIGINS`` to be a comma-separated string in the env."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def async_database_url(self) -> str:
        """The DSN rewritten to use the asyncpg driver (for the FastAPI engine)."""
        return _with_driver(self.database_url, "postgresql+asyncpg")

    @property
    def sync_database_url(self) -> str:
        """The DSN rewritten to use the psycopg (v3) driver (for Dagster/Alembic)."""
        return _with_driver(self.database_url, "postgresql+psycopg")

    @property
    def is_prod(self) -> bool:
        """Whether we are running in the production environment."""
        return self.environment == "prod"


def _with_driver(url: str, driver: str) -> str:
    """Return ``url`` with its scheme replaced by ``driver``.

    Accepts a bare ``postgresql://`` (or ``postgres://``) DSN, or one that
    already carries a ``+driver`` suffix, and normalises it to ``driver``.
    """
    scheme, sep, rest = url.partition("://")
    if not sep:
        # Not a URL we recognise; hand it back unchanged for the caller to fail on.
        return url
    return f"{driver}://{rest}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a process-wide cached :class:`Settings` instance.

    Cached so that the environment is read once. Tests may call
    ``get_settings.cache_clear()`` to force a reload.
    """
    return Settings()  # type: ignore[call-arg]  # values are sourced from the environment


settings = get_settings()
"""Eagerly-instantiated settings for convenient ``from ... import settings`` use."""
