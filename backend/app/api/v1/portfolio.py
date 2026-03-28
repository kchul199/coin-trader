from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import uuid

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.portfolio import Portfolio
from app.models.balance import Balance

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


class PortfolioItem(BaseModel):
    id: uuid.UUID
    symbol: str
    exchange_id: str
    quantity: float
    avg_buy_price: Optional[float]
    initial_capital: Optional[float]
    last_updated: datetime

    class Config:
        from_attributes = True


@router.get("", response_model=list[PortfolioItem])
async def get_portfolio(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """보유 현황 조회"""
    result = await db.execute(
        select(Portfolio).where(Portfolio.user_id == current_user.id)
    )
    return result.scalars().all()
