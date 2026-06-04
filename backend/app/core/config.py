"""
core/config.py
──────────────
Central configuration module using Pydantic BaseSettings.
All values are loaded from environment variables / .env file.
A singleton `settings` object is exported for use throughout the app.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────────────────────
    APP_NAME: str = "AI SQL Analysis Tool"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"
    SECRET_KEY: str = "your-super-secret-key-change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # ── JWT (Legacy / New Integration) ──────────────────────────────────────────
    JWT_SECRET_KEY: str = "your-super-secret-key-change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    JWT_ISSUER: str = "sql-analytics-platform"
    JWT_AUDIENCE: str = "sql-analytics-users"

    # ── Query / Execution ─────────────────────────────────────────────────────
    QUERY_TIMEOUT: int = 30          # seconds
    MAX_ROWS: int = 5000

    # ── Allowed databases ─────────────────────────────────────────────────────
    ALLOWED_DATABASES: str = "mysql,postgresql"

    # ── Internal DB (query history) ───────────────────────────────────────────
    INTERNAL_DB_URL: str = "sqlite:///./sql_tool.db"

    # ── CORS ──────────────────────────────────────────────────────────────────
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8501"

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_FOLDER: str = "logs"

    # ── Exports / uploads ─────────────────────────────────────────────────────
    EXPORT_FOLDER: str = "exports"
    UPLOAD_FOLDER: str = "uploads"

    # ── Derived / parsed properties ───────────────────────────────────────────
    @property
    def allowed_databases_list(self) -> List[str]:
        """Return ALLOWED_DATABASES as a list of lower-cased strings."""
        return [db.strip().lower() for db in self.ALLOWED_DATABASES.split(",")]

    @property
    def cors_origins_list(self) -> List[str]:
        """Return CORS_ORIGINS as a list of strings."""
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    # ── Validators ────────────────────────────────────────────────────────────
    @field_validator("QUERY_TIMEOUT")
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("QUERY_TIMEOUT must be a positive integer.")
        return v

    @field_validator("MAX_ROWS")
    @classmethod
    def validate_max_rows(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("MAX_ROWS must be a positive integer.")
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached singleton Settings instance."""
    return Settings()


# Module-level singleton — import this across the app
settings: Settings = get_settings()
