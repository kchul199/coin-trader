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
    EXCHANGE_ID: str = "binance"
    USE_TESTNET: bool = True
    QUOTE_CURRENCY: str = "USDT"

    # Anthropic
    ANTHROPIC_API_KEY: str = ""
    AI_CONSULT_TIMEOUT_SECONDS: int = 5

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"

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
