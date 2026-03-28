from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
import uuid

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.strategy import Strategy
from app.schemas.strategy import StrategyCreate, StrategyUpdate, StrategyResponse

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.get("", response_model=list[StrategyResponse])
async def list_strategies(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Strategy).where(Strategy.user_id == current_user.id)
        .order_by(Strategy.created_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=StrategyResponse, status_code=status.HTTP_201_CREATED)
async def create_strategy(
    data: StrategyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    strategy = Strategy(
        user_id=current_user.id,
        name=data.name,
        symbol=data.symbol,
        timeframe=data.timeframe,
        condition_tree=data.condition_tree,
        order_config=data.order_config,
        exit_condition=data.exit_condition,
        ai_mode=data.ai_mode,
        priority=data.priority,
        hold_retry_interval=data.hold_retry_interval,
        hold_max_retry=data.hold_max_retry,
        is_active=False,
    )
    db.add(strategy)
    await db.commit()
    await db.refresh(strategy)
    return strategy


@router.get("/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(
    strategy_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Strategy).where(
            Strategy.id == strategy_id,
            Strategy.user_id == current_user.id,
        )
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="전략을 찾을 수 없습니다.")
    return strategy


@router.put("/{strategy_id}", response_model=StrategyResponse)
async def update_strategy(
    strategy_id: uuid.UUID,
    data: StrategyUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Strategy).where(
            Strategy.id == strategy_id,
            Strategy.user_id == current_user.id,
        )
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="전략을 찾을 수 없습니다.")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(strategy, field, value)
    strategy.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(strategy)
    return strategy


@router.delete("/{strategy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_strategy(
    strategy_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Strategy).where(
            Strategy.id == strategy_id,
            Strategy.user_id == current_user.id,
        )
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="전략을 찾을 수 없습니다.")

    await db.delete(strategy)
    await db.commit()


@router.post("/{strategy_id}/toggle", response_model=StrategyResponse)
async def toggle_strategy(
    strategy_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """전략 활성화/비활성화"""
    result = await db.execute(
        select(Strategy).where(
            Strategy.id == strategy_id,
            Strategy.user_id == current_user.id,
        )
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="전략을 찾을 수 없습니다.")

    strategy.is_active = not strategy.is_active
    strategy.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(strategy)
    return strategy
