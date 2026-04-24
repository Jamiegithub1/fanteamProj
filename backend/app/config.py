from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Fantasy Odds Projections"
    database_url: str = Field(
        default="postgresql+psycopg://fantasy:fantasy_dev_password@localhost:5432/fantasy_odds",
        validation_alias="DATABASE_URL",
    )
    playzilla_enabled: bool = Field(default=True, validation_alias="PLAYZILLA_ENABLED")
    playzilla_base_url: str = Field(default="https://playzilla.com", validation_alias="PLAYZILLA_BASE_URL")
    playzilla_timeout_seconds: float = Field(default=15.0, validation_alias="PLAYZILLA_TIMEOUT_SECONDS")
    playzilla_refresh_interval_seconds: int = Field(
        default=900, validation_alias="PLAYZILLA_REFRESH_INTERVAL_SECONDS"
    )
    draftkings_enabled: bool = Field(default=False, validation_alias="DRAFTKINGS_ENABLED")
    draftkings_base_url: str = Field(
        default="https://sportsbook.draftkings.com",
        validation_alias="DRAFTKINGS_BASE_URL",
    )
    draftkings_region: str = Field(default="US-NJ-SB", validation_alias="DRAFTKINGS_REGION")
    draftkings_timeout_seconds: float = Field(default=15.0, validation_alias="DRAFTKINGS_TIMEOUT_SECONDS")
    draftkings_refresh_interval_seconds: int = Field(
        default=900, validation_alias="DRAFTKINGS_REFRESH_INTERVAL_SECONDS"
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
