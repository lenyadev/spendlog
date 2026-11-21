from datetime import timedelta
from enum import StrEnum
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LogLevel(StrEnum):
    INFO = "INFO"
    DEBUG = "DEBUG"
    WARNING = "WARNING"
    ERROR = "ERROR"


class Settings(BaseSettings):
    app_name: str = "Spendlog API"
    app_env: str = "development"
    app_version: str = "0.1.0"
    database_url: str
    test_database_url: str | None = None
    secret_key: str
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14
    cookie_secure: bool = True
    cookie_samesite: Literal["lax", "strict", "none"] = "strict"
    log_level: LogLevel = LogLevel.INFO
    cors_origins: list[str] = Field(default_factory=list)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def refresh_token_ttl(self) -> timedelta:
        return timedelta(days=self.refresh_token_expire_days)

    @property
    def cookie_max_age(self) -> int:
        return int(self.refresh_token_ttl.total_seconds())


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore
