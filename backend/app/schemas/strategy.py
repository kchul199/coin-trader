from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Any
import uuid


class StrategyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    symbol: str = Field(..., examples=["BTC/USDT"])
    timeframe: str = Field("1h", pattern="^(1m|5m|15m|30m|1h|4h|1d)$")
    condition_tree: dict = Field(..., description="매수 조건 트리 (JSON)")
    order_config: dict = Field(..., description="주문 설정 (JSON)")
    exit_condition: Optional[dict] = None
    ai_mode: str = Field("off", pattern="^(off|auto|semi_auto|observe)$")
    priority: int = Field(5, ge=1, le=10)
    hold_retry_interval: int = Field(300, ge=60)
    hold_max_retry: int = Field(3, ge=1, le=10)


class StrategyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    symbol: Optional[str] = None
    timeframe: Optional[str] = Field(None, pattern="^(1m|5m|15m|30m|1h|4h|1d)$")
    condition_tree: Optional[dict] = None
    order_config: Optional[dict] = None
    exit_condition: Optional[dict] = None
    ai_mode: Optional[str] = Field(None, pattern="^(off|auto|semi_auto|observe)$")
    priority: Optional[int] = Field(None, ge=1, le=10)
    hold_retry_interval: Optional[int] = Field(None, ge=60)
    hold_max_retry: Optional[int] = Field(None, ge=1, le=10)
    is_active: Optional[bool] = None


class StrategyResponse(BaseModel):
    id: uuid.UUID
    name: str
    symbol: str
    timeframe: str
    condition_tree: Any
    order_config: Any
    exit_condition: Optional[Any]
    ai_mode: str
    priority: int
    hold_retry_interval: int
    hold_max_retry: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
