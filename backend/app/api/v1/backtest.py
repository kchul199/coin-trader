"""
백테스트 API
- POST /backtest/run: 백테스트 실행 (Celery 비동기)
- GET  /backtest/status/{job_id}: 실행 상태 조회
- GET  /backtest/{id}: 결과 조회
- GET  /backtest/history: 내 백테스트 이력
"""
from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.core.redis_client import get_redis
from app.models.user import User
from app.models.backtest_result import BacktestResult
from app.models.strategy import Strategy
from app.services.backtest_service import BacktestService

router = APIRouter(prefix="/backtest", tags=["backtest"])


# ───────────────────────────── Schemas ──────────────────────────────

class BacktestRunRequest(BaseModel):
    strategy_id: str
    start_date: date
    end_date: date
    initial_capital: float = Field(default=10000.0, gt=0)
    commission_pct: float = Field(default=0.05, ge=0, le=5)
    slippage_pct: float = Field(default=0.02, ge=0, le=5)


# ───────────────────────────── Endpoints ────────────────────────────

@router.post("/run", summary="백테스트 실행")
async def run_backtest(
    req: BacktestRunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis=Depends(get_redis),
):
    """전략 백테스트를 Celery 태스크로 비동기 실행합니다."""
    # 전략 소유권 확인
    result = await db.execute(
        select(Strategy).where(
            Strategy.id == uuid.UUID(req.strategy_id),
            Strategy.user_id == current_user.id,
        )
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="전략을 찾을 수 없습니다")

    # 날짜 유효성 검사
    if req.start_date >= req.end_date:
        raise HTTPException(status_code=400, detail="시작일은 종료일보다 이전이어야 합니다")

    job_id = str(uuid.uuid4())

    # Redis에 대기 상태 저장
    await redis.hset(
        f"backtest:{job_id}",
        mapping={"status": "pending", "strategy_id": req.strategy_id},
    )
    await redis.expire(f"backtest:{job_id}", 3600)

    # Celery 태스크 디스패치
    from app.tasks.backtest_tasks import run_backtest_task
    run_backtest_task.apply_async(
        kwargs={
            "backtest_result_id": job_id,
            "strategy_id": req.strategy_id,
            "user_id": str(current_user.id),
            "start_date_str": req.start_date.isoformat(),
            "end_date_str": req.end_date.isoformat(),
            "initial_capital": req.initial_capital,
            "commission_pct": req.commission_pct,
            "slippage_pct": req.slippage_pct,
        },
        task_id=job_id,
        priority=5,
    )

    return {"job_id": job_id, "status": "pending"}


@router.get("/status/{job_id}", summary="백테스트 실행 상태")
async def get_backtest_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
    redis=Depends(get_redis),
):
    """Redis에서 백테스트 작업 상태를 조회합니다."""
    data = await redis.hgetall(f"backtest:{job_id}")
    if not data:
        raise HTTPException(status_code=404, detail="백테스트 작업을 찾을 수 없습니다")

    return {
        "job_id": job_id,
        "status": data.get("status", "unknown"),
        "result_id": data.get("result_id"),
        "error": data.get("error"),
        "total_return_pct": float(data["total_return_pct"]) if data.get("total_return_pct") else None,
    }


@router.get("/history", summary="백테스트 이력")
async def list_backtest_history(
    strategy_id: Optional[str] = Query(None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """내 백테스트 결과 목록을 조회합니다."""
    # 내 전략 ID 목록
    strategy_result = await db.execute(
        select(Strategy.id).where(Strategy.user_id == current_user.id)
    )
    my_strategy_ids = [row[0] for row in strategy_result.all()]

    if not my_strategy_ids:
        return {"items": [], "total": 0, "limit": limit, "offset": offset}

    query = select(BacktestResult).where(
        BacktestResult.strategy_id.in_(my_strategy_ids)
    )

    if strategy_id:
        try:
            query = query.where(BacktestResult.strategy_id == uuid.UUID(strategy_id))
        except ValueError:
            pass

    # 전체 개수
    from sqlalchemy import func
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # 페이지네이션
    query = query.order_by(desc(BacktestResult.created_at)).limit(limit).offset(offset)
    items = (await db.execute(query)).scalars().all()

    return {
        "items": [BacktestService.serialize_result(r) for r in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{backtest_id}", summary="백테스트 결과 상세")
async def get_backtest_result(
    backtest_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """특정 백테스트 결과를 조회합니다."""
    try:
        bid = uuid.UUID(backtest_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="잘못된 백테스트 ID")

    # 소유권 확인: 내 전략의 결과인지 검사
    result = await db.execute(
        select(BacktestResult)
        .join(Strategy, BacktestResult.strategy_id == Strategy.id)
        .where(
            BacktestResult.id == bid,
            Strategy.user_id == current_user.id,
        )
    )
    backtest = result.scalar_one_or_none()
    if not backtest:
        raise HTTPException(status_code=404, detail="백테스트 결과를 찾을 수 없습니다")

    return BacktestService.serialize_result(backtest)
