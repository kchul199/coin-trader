"""
긴급 정지 API
- POST /emergency/stop/{strategy_id}: 전략 긴급 정지
- POST /emergency/stop/global: 전체 전략 긴급 정지
- DELETE /emergency/stop/{strategy_id}: 긴급 정지 해제
- GET /emergency/status: 현재 정지 상태 조회
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.core.redis_client import get_redis
from app.models.user import User

router = APIRouter(prefix="/emergency", tags=["emergency"])


class EmergencyStopRequest(BaseModel):
    reason: str = "사용자 요청"


# ------------------------------------------------------------------ #
# 전략 긴급 정지
# ------------------------------------------------------------------ #

@router.post("/stop/{strategy_id}", summary="전략 긴급 정지")
async def stop_strategy(
    strategy_id: str,
    body: EmergencyStopRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    """
    해당 전략을 즉시 비활성화하고 미체결 주문을 모두 취소한다.
    Celery 비동기 태스크로 처리하여 빠른 응답을 보장한다.
    """
    from app.tasks.trading_tasks import emergency_stop_task

    # 소유권 확인
    from sqlalchemy import select
    from app.models.strategy import Strategy
    result = await db.execute(
        select(Strategy).where(
            Strategy.id == strategy_id,
            Strategy.user_id == current_user.id,
        )
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="전략을 찾을 수 없습니다.",
        )

    # Celery 비동기 처리
    task = emergency_stop_task.apply_async(
        args=[strategy_id, str(current_user.id), body.reason],
        queue="trading",
        priority=9,  # 최우선 처리
    )

    return {
        "message": "긴급 정지 요청이 접수되었습니다.",
        "strategy_id": strategy_id,
        "task_id": task.id,
    }


@router.post("/stop/global", summary="전체 전략 긴급 정지")
async def stop_all_strategies(
    body: EmergencyStopRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    """모든 활성 전략을 즉시 정지한다."""
    from sqlalchemy import select, update
    from app.models.strategy import Strategy

    # 글로벌 긴급 정지 플래그
    await redis.setex("emergency:stop:global", 3600, body.reason)

    # 모든 활성 전략 비활성화
    await db.execute(
        update(Strategy)
        .where(Strategy.user_id == current_user.id, Strategy.is_active.is_(True))
        .values(is_active=False)
    )
    await db.commit()

    # 개별 정지 태스크 디스패치
    from app.tasks.trading_tasks import emergency_stop_task
    result = await db.execute(
        select(Strategy.id).where(Strategy.user_id == current_user.id)
    )
    strategy_ids = [str(row[0]) for row in result.fetchall()]

    for sid in strategy_ids:
        emergency_stop_task.apply_async(
            args=[sid, str(current_user.id), body.reason],
            queue="trading",
            priority=9,
        )

    return {
        "message": "전체 긴급 정지가 요청되었습니다.",
        "strategies_stopped": len(strategy_ids),
    }


@router.delete("/stop/{strategy_id}", summary="긴급 정지 해제")
async def clear_stop(
    strategy_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    """긴급 정지 플래그를 해제하고 전략을 재활성화할 수 있는 상태로 복원한다."""
    from sqlalchemy import select
    from app.models.strategy import Strategy

    # 소유권 확인
    result = await db.execute(
        select(Strategy).where(
            Strategy.id == strategy_id,
            Strategy.user_id == current_user.id,
        )
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="전략을 찾을 수 없습니다.",
        )

    await redis.delete(f"emergency:stop:{strategy_id}")
    return {"message": "긴급 정지가 해제되었습니다.", "strategy_id": strategy_id}


@router.get("/status", summary="긴급 정지 상태 조회")
async def get_stop_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    """전략별 긴급 정지 상태 및 글로벌 상태를 반환한다."""
    from sqlalchemy import select
    from app.models.strategy import Strategy

    result = await db.execute(
        select(Strategy.id, Strategy.name).where(Strategy.user_id == current_user.id)
    )
    strategies = result.fetchall()

    global_stop_raw = await redis.get("emergency:stop:global")
    global_stop = global_stop_raw.decode() if global_stop_raw else None

    statuses = []
    for s_id, s_name in strategies:
        flag_raw = await redis.get(f"emergency:stop:{s_id}")
        statuses.append({
            "strategy_id": str(s_id),
            "strategy_name": s_name,
            "stopped": flag_raw is not None,
            "reason": flag_raw.decode() if flag_raw else None,
        })

    return {
        "global_stop": global_stop is not None,
        "global_stop_reason": global_stop,
        "strategies": statuses,
    }
