from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Fantasy Odds Projections"
    database_url: str = Field(
        default="postgresql+psycopg://fantasy:fantasy_dev_password@localhost:5432/fantasy_odds",
        validation_alias="DATABASE_URL",
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
