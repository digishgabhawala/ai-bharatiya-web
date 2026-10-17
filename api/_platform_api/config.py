"""Settings for the platform API, read from the environment."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    database_url: str = ""
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    # Bootstrap only: read by scripts/apply_platform_migrations.py, not by routes.
    platform_admin_emails: str = ""
    auth_cache_minutes: float = 15


settings = Settings()
