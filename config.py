# config.py
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # База данных
    DATABASE_URL: str = "sqlite+aiosqlite:///./hotels.db"
    # или postgresql+asyncpg://user:password@localhost:5432/hotels_db

    # для продакшена лучше брать из переменных окружения
    PROJECT_NAME: str = "Hotel Booking API"
    API_V1_STR: str = "/api/v1"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()