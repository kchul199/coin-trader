from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
import uuid


class ExchangeAccountCreate(BaseModel):
    exchange_id: str = Field(..., pattern="^(binance|upbit|bithumb)$")
    api_key: str = Field(..., min_length=1)
    api_secret: str = Field(..., min_length=1)
    is_testnet: bool = True


class ExchangeAccountResponse(BaseModel):
    id: uuid.UUID
    exchange_id: str
    is_testnet: bool
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class BalanceItem(BaseModel):
    symbol: str
    available: float
    locked: float
    total: float


class BalanceResponse(BaseModel):
    exchange_id: str
    is_testnet: bool
    balances: list[BalanceItem]
    synced_at: str
