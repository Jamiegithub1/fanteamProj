from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Fantasy Odds Projections"
    database_url: str = Field(
        default="postgresql+psycopg://fantasy:fantasy_dev_password@localhost:5432/fantasy_odds",
        validation_alias="DATABASE_URL",
    )
    app_username: str = Field(default="admin", validation_alias="APP_USERNAME")
    app_password: str = Field(default="change-me", validation_alias="APP_PASSWORD")
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
    balldontlie_enabled: bool = Field(default=False, validation_alias="BALLDONTLIE_ENABLED")
    balldontlie_api_key: str = Field(default="", validation_alias="BALLDONTLIE_API_KEY")
    balldontlie_base_url: str = Field(default="https://api.balldontlie.io", validation_alias="BALLDONTLIE_BASE_URL")
    balldontlie_timeout_seconds: float = Field(default=15.0, validation_alias="BALLDONTLIE_TIMEOUT_SECONDS")
    balldontlie_refresh_interval_seconds: int = Field(
        default=900, validation_alias="BALLDONTLIE_REFRESH_INTERVAL_SECONDS"
    )
    propline_enabled: bool = Field(default=False, validation_alias="PROPLINE_ENABLED")
    propline_api_key: str = Field(default="", validation_alias="PROPLINE_API_KEY")
    propline_base_url: str = Field(default="https://api.prop-line.com", validation_alias="PROPLINE_BASE_URL")
    propline_timeout_seconds: float = Field(default=15.0, validation_alias="PROPLINE_TIMEOUT_SECONDS")
    propline_refresh_interval_seconds: int = Field(default=900, validation_alias="PROPLINE_REFRESH_INTERVAL_SECONDS")
    betmgm_enabled: bool = Field(default=False, validation_alias="BETMGM_ENABLED")
    betmgm_base_url: str = Field(default="https://sportsapi.co.betmgm.com", validation_alias="BETMGM_BASE_URL")
    betmgm_access_id: str = Field(default="", validation_alias="BETMGM_ACCESS_ID")
    betmgm_access_token: str = Field(default="", validation_alias="BETMGM_ACCESS_TOKEN")
    betmgm_country: str = Field(default="US", validation_alias="BETMGM_COUNTRY")
    betmgm_sport_id: str = Field(default="", validation_alias="BETMGM_SPORT_ID")
    betmgm_timeout_seconds: float = Field(default=15.0, validation_alias="BETMGM_TIMEOUT_SECONDS")
    betmgm_refresh_interval_seconds: int = Field(default=900, validation_alias="BETMGM_REFRESH_INTERVAL_SECONDS")
    scheduler_enabled: bool = Field(default=True, validation_alias="SCHEDULER_ENABLED")
    scheduler_regular_interval_seconds: int = Field(default=1800, validation_alias="SCHEDULER_REGULAR_INTERVAL_SECONDS")
    scheduler_prelock_interval_seconds: int = Field(default=300, validation_alias="SCHEDULER_PRELOCK_INTERVAL_SECONDS")
    scheduler_initial_delay_seconds: int = Field(default=30, validation_alias="SCHEDULER_INITIAL_DELAY_SECONDS")
    scheduler_prelock_window_minutes: int = Field(default=60, validation_alias="SCHEDULER_PRELOCK_WINDOW_MINUTES")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
