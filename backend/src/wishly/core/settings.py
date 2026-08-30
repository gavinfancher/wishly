"""Application settings, loaded from environment variables via pydantic-settings.

All configuration is supplied through the environment (never hard-coded). The
canonical list of variables lives in the ``.env.example`` files. Required values
raise a clear validation error the first time :func:`get_settings` runs.

This is the *only* place the environment is read. Everything the API, the worker,
and the CLIs need is a field or a property on :class:`Settings`.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

Environment = Literal["dev", "prod"]

# Identity used when the local dev auth bypass is active (see ``dev_auth_bypass``).
DEV_USER_SUB = "user_dev_local"
DEV_USER_EMAIL = "dev@wishly.local"
DEV_USER_FIRST_NAME = "Dev"
DEV_USER_LAST_NAME = "User"


class Settings(BaseSettings):
    """Strongly-typed application configuration.

    Reads from the process environment and, for local development, from a
    ``.env`` file. Field names are case-insensitive against env var names.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Database (API uses asyncpg; worker/CLIs use sync psycopg) -----------
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
    # REQUIRED in production: the Frontend API origin doubles as the token issuer
    # and the JWKS source. Without it the API cannot verify a single token and
    # every authenticated request 401s while the app otherwise looks healthy.
    clerk_frontend_api: str | None = Field(
        default=None,
        validation_alias=AliasChoices("clerk_frontend_api", "clerk_issuer"),
        description="Clerk Frontend API origin, e.g. https://clerk.wishly.dev.",
    )
    clerk_jwks_url: str | None = Field(
        default=None,
        description="JWKS endpoint. Derived from clerk_frontend_api when unset.",
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
    auth_dev_bypass: bool = Field(
        default=False,
        description="Skip Clerk verification and authenticate a fixed dev user. Never in prod.",
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Allow ``ALLOWED_ORIGINS`` to be a comma-separated string in the env."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("clerk_frontend_api", mode="after")
    @classmethod
    def _normalize_origin(cls, value: str | None) -> str | None:
        """Accept ``clerk.wishly.dev`` or a full URL, with or without a trailing slash."""
        if not value:
            return None
        value = value.rstrip("/")
        return value if value.startswith("http") else f"https://{value}"

    @property
    def is_prod(self) -> bool:
        """Whether we are running in the production environment."""
        return self.environment == "prod"

    @property
    def async_database_url(self) -> str:
        """The DSN rewritten to use the asyncpg driver (for the FastAPI engine)."""
        return _with_driver(self.database_url, "postgresql+asyncpg", ssl_param="ssl")

    @property
    def sync_database_url(self) -> str:
        """The DSN rewritten to use the psycopg (v3) driver (for the worker/CLIs)."""
        return _with_driver(self.database_url, "postgresql+psycopg", ssl_param="sslmode")

    @property
    def dev_auth_bypass(self) -> bool:
        """Whether to skip Clerk verification and authenticate a fixed dev user.

        For running the UI against a real backend **without Clerk**. Requires
        ``AUTH_DEV_BYPASS`` *and* a non-prod ``ENVIRONMENT``, so it can never
        weaken a prod deployment even if the flag leaks into a prod env file.
        """
        return self.auth_dev_bypass and not self.is_prod

    @property
    def clerk_issuer(self) -> str | None:
        """Expected ``iss`` claim for Clerk session tokens (the Frontend API origin)."""
        return self.clerk_frontend_api

    @property
    def jwks_url(self) -> str | None:
        """The JWKS endpoint to fetch Clerk's signing keys from.

        Uses ``CLERK_JWKS_URL`` verbatim if set; otherwise derives it from the
        Frontend API origin. ``None`` when neither is configured.
        """
        if self.clerk_jwks_url:
            return self.clerk_jwks_url
        if self.clerk_frontend_api:
            return f"{self.clerk_frontend_api}/.well-known/jwks.json"
        return None


def _with_driver(url: str, driver: str, *, ssl_param: str) -> str:
    """Return ``url`` with its scheme replaced by ``driver`` and TLS spelled right.

    Accepts a bare ``postgresql://`` (or ``postgres://``) DSN, or one that already
    carries a ``+driver`` suffix, and normalises it to ``driver``.

    The two drivers disagree about how to ask for TLS, and neither tolerates the
    other's spelling:

    * **psycopg** (worker, schema, psql) uses libpq's ``sslmode``. Given ``ssl``
      it raises ``invalid connection option "ssl"``.
    * **asyncpg** (the API) takes ``ssl``. Given ``sslmode`` it raises
      ``TypeError: connect() got an unexpected keyword argument 'sslmode'`` — on
      every request, because the failure is at connect time.

    So a single ``DATABASE_URL`` cannot be handed to both verbatim. We take
    libpq's ``sslmode`` as the canonical spelling in the environment (it is what
    RDS, psql, and every runbook use) and rename the key here per driver. The
    *values* share one vocabulary — ``disable``, ``allow``, ``prefer``,
    ``require``, ``verify-ca``, ``verify-full`` — so only the key moves.
    """
    scheme, sep, rest = url.partition("://")
    if not sep:
        # Not a URL we recognise; hand it back unchanged for the caller to fail on.
        return url
    parts = urlsplit(f"{driver}://{rest}")
    if not parts.query:
        return urlunsplit(parts)
    query = [
        (ssl_param if key in ("sslmode", "ssl") else key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
    ]
    return urlunsplit(parts._replace(query=urlencode(query)))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a process-wide cached :class:`Settings` instance.

    Cached so the environment is read once. Tests may call
    ``get_settings.cache_clear()`` to force a reload.
    """
    return Settings()  # type: ignore[call-arg]  # values are sourced from the environment


settings = get_settings()
"""Eagerly-instantiated settings for convenient ``from ... import settings`` use."""
