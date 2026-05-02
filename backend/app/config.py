import os
from pydantic_settings import BaseSettings
from pydantic import model_validator

ALLOWED_EXCHANGE_IDS = {"binance", "upbit", "bithumb"}


class Settings(BaseSettings):
    """Application configuration using pydantic-settings."""

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://cointrader:secret@localhost/cointrader"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    JWT_SECRET_KEY: str = "dev-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Exchange
    EXCHANGE_ID: str = "upbit"
    USE_TESTNET: bool = False
    QUOTE_CURRENCY: str = "KRW"
    MIN_QUOTE_BALANCE: float = 10000.0
    EXCHANGE_HTTP_TIMEOUT_MS: int = 10000
    EXCHANGE_RETRY_MAX_ATTEMPTS: int = 4
    EXCHANGE_RETRY_BASE_DELAY_SECONDS: float = 1.5
    EXCHANGE_RETRY_MAX_DELAY_SECONDS: float = 15.0
    POSITION_WATCH_INTERVAL_SECONDS: int = 2
    POSITION_WATCH_EVENT_THROTTLE_SECONDS: int = 1
    BALANCE_RESERVATION_TTL_SECONDS: int = 3600

    # Anthropic
    ANTHROPIC_API_KEY: str = ""
    AI_CONSULT_TIMEOUT_SECONDS: int = 5

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_TASK_MAX_RETRIES: int = 4
    CELERY_RETRY_BASE_DELAY_SECONDS: int = 5
    CELERY_RETRY_MAX_DELAY_SECONDS: int = 60

    # API
    API_V1_STR: str = "/api/v1"

    @model_validator(mode="after")
    def validate_exchange_id(self):
        if self.EXCHANGE_ID not in ALLOWED_EXCHANGE_IDS:
            raise ValueError(f"허용되지 않은 거래소: {self.EXCHANGE_ID}")
        return self

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
