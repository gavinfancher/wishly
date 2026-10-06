"""Typed configuration, loaded from WISHLY_* environment variables.

This file is the complete list of knobs an operator can turn. In production
every value comes from Infisical (`infisical run -- docker compose up -d`).
"""

from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # WISHLY_ENV=prod in the environment becomes settings.env == "prod".
    # A .env file is read too, for local development.
    model_config = SettingsConfigDict(env_prefix="WISHLY_", env_file=".env")

    env: Literal["local", "test", "prod"] = "local"
    # The git SHA, set at image build time, so /healthz shows which build is live.
    version: str = "dev"

    # Required: no default, so the app refuses to start without it.
    # SecretStr prints as '**********', so it can't leak into logs by accident.
    database_url: SecretStr
    # Max open connections. PlanetScale caps connections per plan.
    db_pool_size: int = 5

    # Clerk instance URL, e.g. https://clerk.wishly.dev. Session tokens must be
    # issued by it, and its public signing keys live under it.
    clerk_issuer: str
    # Browser origins allowed to call the API (the frontend's URL).
    cors_origins: list[str] = ["http://localhost:5173"]

    # EventBridge sends this as a Bearer token to POST /internal/run.
    run_token: SecretStr

    # Unset locally: emails are printed instead of sent.
    resend_api_key: SecretStr | None = None
    email_from: str = "Wishly <reminders@wishly.dev>"
