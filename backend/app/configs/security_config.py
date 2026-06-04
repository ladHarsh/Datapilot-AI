from pydantic_settings import BaseSettings, SettingsConfigDict

class SecurityConfig(BaseSettings):
    """Configuration for global security thresholds and limits."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # ── Protection Limits ─────────────────────────────────────────────────────
    QUERY_TIMEOUT_SECONDS: int = 30
    MAX_ROWS_RETRIEVAL: int = 100000
    MAX_JOINS_ALLOWED: int = 5
    MAX_QUERY_LENGTH_CHARS: int = 5000

    # ── API Protection ───────────────────────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: int = 100
    MAX_PAYLOAD_SIZE_MB: int = 1
    ENABLE_SECURE_HEADERS: bool = True

security_settings = SecurityConfig()
