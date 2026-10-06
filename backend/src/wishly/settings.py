"""Typed configuration, loaded from WISHLY_* environment variables.

This file is the complete list of knobs an operator can turn.
"""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # WISHLY_ENV=prod in the environment becomes settings.env == "prod".
    # A .env file is read too, for local development.
    model_config = SettingsConfigDict(env_prefix="WISHLY_", env_file=".env")

    env: Literal["local", "test", "prod"] = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    # The git SHA, set at image build time, so /healthz shows which build is live.
    version: str = "dev"
