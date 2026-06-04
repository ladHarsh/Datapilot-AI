import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class JWTConfig(BaseSettings):
    """Configuration for JWT and authentication security."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    JWT_SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION_TO_A_SECURE_RANDOM_HEX"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    JWT_ISSUER: str = "sql-analytics-platform"
    JWT_AUDIENCE: str = "sql-analytics-users"

jwt_settings = JWTConfig()
