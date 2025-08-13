from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    # Application
    app_name: str = 'Orion AI Platform Backend'
    app_version: str = '0.1.0'

    # Database
    database_url: str = Field(default='postgresql+psycopg://postgres:root@localhost:5433/orion_ai_dev_v2', alias='DATABASE_URL')

    # Security / Encryption
    secret_key: str = Field(default='change-me-in-prod', alias='SECRET_KEY')

    # Pagination
    default_page_size: int = 20
    max_page_size: int = 100

    # Datasource specific
    datasource_test_timeout_s: int = 10
    datasource_test_timeout_max_s: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


