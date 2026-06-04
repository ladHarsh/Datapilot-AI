from pydantic_settings import BaseSettings, SettingsConfigDict

class MonitoringConfig(BaseSettings):
    """Configuration for security auditing and metrics."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    ENABLE_AUDIT_LOGGING: bool = True
    AUDIT_LOG_FORMAT: str = "json"
    SLOW_QUERY_THRESHOLD_MS: int = 2000
    METRICS_RETENTION_DAYS: int = 30

monitoring_settings = MonitoringConfig()
