from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import uuid

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.order import Order
from app.models.strategy import Strategy

router = APIRouter(prefix="/orders", tags=["orders"])


class OrderResponse(BaseModel):
    id: uuid.UUID
    symbol: str
    side: str
    order_type: str
    price: Optional[float]
    quantity: float
    filled_quantity: float
    status: str
    created_at: datetime
    filled_at: Optional[datetime]

    class Config:
        from_attributes = True


@router.get("", response_model=list[OrderResponse])
async def list_orders(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """주문 내역 (페이지네이션)"""
    offset = (page - 1) * size
    result = await db.execute(
        select(Order)
        .join(Strategy)
        .where(Strategy.user_id == current_user.id)
        .order_by(desc(Order.created_at))
        .offset(offset)
        .limit(size)
    )
    return result.scalars().all()
