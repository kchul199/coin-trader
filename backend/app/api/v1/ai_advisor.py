"""
AI 자문 API
- GET /ai-advisor/consultations: 자문 내역 조회 (페이지네이션)
- GET /ai-advisor/consultations/{strategy_id}/latest: 특정 전략의 최신 자문
- GET /ai-advisor/cache/{strategy_id}: Redis 캐시 자문 조회
- POST /ai-advisor/refresh/{strategy_id}: 자문 강제 갱신
- GET /ai-advisor/stats: AI 자문 통계
"""
from __future__ import annotations

import json
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.core.redis_client import get_redis
from app.models.user import User
from app.models.ai_consultation import AIConsultation as AiConsultation
from app.models.strategy import Strategy
from app.trading.ai_consultant import AIConsultant, APPROVAL_KEY_PREFIX

router = APIRouter(prefix="/ai-advisor", tags=["ai-advisor"])


# ------------------------------------------------------------------ #
# 자문 내역 조회
# ------------------------------------------------------------------ #

@router.get("/consultations", summary="AI 자문 내역 조회")
async def list_consultations(
    strategy_id: Optional[str] = Query(None, description="전략 ID 필터"),
    decision: Optional[str] = Query(None, description="결정 필터: execute|hold|avoid"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    사용자의 AI 자문 내역을 최신순으로 반환한다.
    전략 ID 또는 결정(execute/hold/avoid)으로 필터링 가능.
    """
    # 사용자 소유 전략 ID 목록
    strat_result = await db.execute(
        select(Strategy.id).where(Strategy.user_id == current_user.id)
    )
    owned_strategy_ids = [str(row[0]) for row in strat_result.fetchall()]

    if not owned_strategy_ids:
        return {"items": [], "total": 0, "limit": limit, "offset": offset}

    query = select(AiConsultation).where(
        AiConsultation.strategy_id.in_(owned_strategy_ids)
    )

    if strategy_id:
        query = query.where(AiConsultation.strategy_id == strategy_id)
    if decision and decision in ("execute", "hold", "avoid"):
        query = query.where(AiConsultation.decision == decision)

    # 전체 카운트
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar_one()

    # 페이지 조회
    query = query.order_by(desc(AiConsultation.created_at)).limit(limit).offset(offset)
    result = await db.execute(query)
    items = result.scalars().all()

    return {
        "items": [
            {
                "id": str(c.id),
                "strategy_id": str(c.strategy_id),
                "order_id": str(c.order_id) if c.order_id else None,
                "model": c.model,
                "decision": c.decision,
                "confidence": c.confidence,
                "reason": c.reason,
                "risk_level": c.risk_level,
                "key_concerns": c.key_concerns,
                "user_approved": c.user_approved,
                "latency_ms": c.latency_ms,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in items
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/consultations/{strategy_id}/latest", summary="전략 최신 AI 자문")
async def get_latest_consultation(
    strategy_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    """특정 전략의 가장 최근 AI 자문 결과를 반환한다. Redis 캐시 우선."""
    # 소유권 확인
    strat_result = await db.execute(
        select(Strategy).where(
            Strategy.id == strategy_id,
            Strategy.user_id == current_user.id,
        )
    )
    strategy = strat_result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="전략 없음")

    # Redis 캐시 조회
    import json
    cached_raw = await redis.get(f"ai:advice:{strategy_id}")
    if cached_raw:
        try:
            cached = json.loads(cached_raw)
            cached["source"] = "cache"
            return cached
        except Exception:
            pass

    # DB에서 최신 조회
    result = await db.execute(
        select(AiConsultation)
        .where(AiConsultation.strategy_id == strategy_id)
        .order_by(desc(AiConsultation.created_at))
        .limit(1)
    )
    consult = result.scalar_one_or_none()
    if not consult:
        return {"source": "none", "message": "자문 내역 없음"}

    return {
        "source": "db",
        "decision": consult.decision,
        "confidence": consult.confidence,
        "reason": consult.reason,
        "risk_level": consult.risk_level,
        "key_concerns": consult.key_concerns,
        "latency_ms": consult.latency_ms,
        "created_at": consult.created_at.isoformat() if consult.created_at else None,
    }


@router.post("/refresh/{strategy_id}", summary="AI 자문 강제 갱신")
async def refresh_consultation(
    strategy_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Celery 태스크를 통해 특정 전략의 AI 자문을 즉시 갱신한다."""
    # 소유권 확인
    strat_result = await db.execute(
        select(Strategy).where(
            Strategy.id == strategy_id,
            Strategy.user_id == current_user.id,
            Strategy.ai_mode != "off",
        )
    )
    strategy = strat_result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="전략을 찾을 수 없거나 AI 모드가 꺼져 있습니다.",
        )

    from app.tasks.ai_tasks import refresh_ai_advice_task
    task = refresh_ai_advice_task.apply_async(
        args=[strategy_id],
        queue="ai_advice",
    )

    return {
        "message": "AI 자문 갱신 요청이 접수되었습니다.",
        "strategy_id": strategy_id,
        "task_id": task.id,
    }


@router.get("/stats", summary="AI 자문 통계")
async def get_ai_stats(
    strategy_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """AI 자문 결정 분포, 평균 신뢰도, 평균 응답 시간 통계를 반환한다."""
    # 사용자 소유 전략
    strat_result = await db.execute(
        select(Strategy.id).where(Strategy.user_id == current_user.id)
    )
    owned_ids = [str(row[0]) for row in strat_result.fetchall()]

    query = select(AiConsultation).where(
        AiConsultation.strategy_id.in_(owned_ids)
    )
    if strategy_id:
        query = query.where(AiConsultation.strategy_id == strategy_id)

    result = await db.execute(query)
    consultations = result.scalars().all()

    if not consultations:
        return {
            "total": 0,
            "decision_distribution": {},
            "avg_confidence": None,
            "avg_latency_ms": None,
            "risk_distribution": {},
        }

    decisions = [c.decision for c in consultations]
    confidences = [c.confidence for c in consultations if c.confidence is not None]
    latencies = [c.latency_ms for c in consultations if c.latency_ms is not None]
    risks = [c.risk_level for c in consultations if c.risk_level]

    return {
        "total": len(consultations),
        "decision_distribution": {
            d: decisions.count(d) for d in ("execute", "hold", "avoid")
        },
        "avg_confidence": round(sum(confidences) / len(confidences), 1) if confidences else None,
        "avg_latency_ms": round(sum(latencies) / len(latencies)) if latencies else None,
        "risk_distribution": {
            r: risks.count(r) for r in ("low", "medium", "high")
        },
    }


@router.get("/approvals", summary="반자동 승인 대기 목록")
async def list_approvals(
    status_filter: str = Query("pending", alias="status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    """반자동(semi_auto) 전략의 승인 대기/승인/거절 요청 목록을 반환한다."""
    strat_result = await db.execute(
        select(Strategy.id, Strategy.name, Strategy.symbol).where(
            Strategy.user_id == current_user.id,
            Strategy.ai_mode == "semi_auto",
        )
    )
    owned = {
        str(row[0]): {"name": row[1], "symbol": row[2]}
        for row in strat_result.fetchall()
    }

    if not owned:
        return {"items": [], "total": 0}

    items = []
    async for key in redis.scan_iter(f"{APPROVAL_KEY_PREFIX}*"):
        raw = await redis.get(key)
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except Exception:
            continue

        strategy_id = str(payload.get("strategy_id"))
        if strategy_id not in owned:
            continue
        if status_filter and payload.get("status") != status_filter:
            continue

        items.append({
            "strategy_id": strategy_id,
            "strategy_name": payload.get("strategy_name") or owned[strategy_id]["name"],
            "symbol": payload.get("symbol") or owned[strategy_id]["symbol"],
            "decision": payload.get("decision"),
            "confidence": payload.get("confidence"),
            "reason": payload.get("reason"),
            "risk_level": payload.get("risk_level"),
            "key_concerns": payload.get("key_concerns") or [],
            "status": payload.get("status"),
            "created_at": payload.get("created_at"),
            "updated_at": payload.get("updated_at"),
        })

    items.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    return {"items": items, "total": len(items)}


async def _update_consultation_approval(
    db: AsyncSession,
    strategy_id: str,
    approved: bool,
) -> None:
    strategy_uuid = uuid.UUID(strategy_id)
    result = await db.execute(
        select(AiConsultation)
        .where(
            AiConsultation.strategy_id == strategy_uuid,
            AiConsultation.user_approved.is_(None),
        )
        .order_by(desc(AiConsultation.created_at))
        .limit(1)
    )
    consult = result.scalar_one_or_none()
    if consult:
        consult.user_approved = approved
        await db.commit()


@router.post("/approvals/{strategy_id}/approve", summary="반자동 자문 승인")
async def approve_ai_request(
    strategy_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    strategy_uuid = uuid.UUID(strategy_id)
    strat_result = await db.execute(
        select(Strategy).where(
            Strategy.id == strategy_uuid,
            Strategy.user_id == current_user.id,
            Strategy.ai_mode == "semi_auto",
        )
    )
    strategy = strat_result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="반자동 전략을 찾을 수 없습니다.")

    consultant = AIConsultant(redis, None)
    approval = await consultant.get_approval_request(strategy_id)
    if not approval or approval.get("status") != "pending":
        raise HTTPException(status_code=404, detail="승인 대기 중인 요청이 없습니다.")

    await consultant.update_approval_status(strategy_id, "approved")
    await _update_consultation_approval(db, strategy_id, True)

    from app.tasks.trading_tasks import evaluate_strategy_task
    task = evaluate_strategy_task.apply_async(args=[strategy_id], queue="trading")

    return {
        "message": "AI 실행 요청이 승인되었습니다.",
        "strategy_id": strategy_id,
        "task_id": task.id,
    }


@router.post("/approvals/{strategy_id}/reject", summary="반자동 자문 거절")
async def reject_ai_request(
    strategy_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    strategy_uuid = uuid.UUID(strategy_id)
    strat_result = await db.execute(
        select(Strategy).where(
            Strategy.id == strategy_uuid,
            Strategy.user_id == current_user.id,
            Strategy.ai_mode == "semi_auto",
        )
    )
    strategy = strat_result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="반자동 전략을 찾을 수 없습니다.")

    consultant = AIConsultant(redis, None)
    approval = await consultant.get_approval_request(strategy_id)
    if not approval or approval.get("status") != "pending":
        raise HTTPException(status_code=404, detail="거절 대기 중인 요청이 없습니다.")

    await consultant.update_approval_status(strategy_id, "rejected")
    await _update_consultation_approval(db, strategy_id, False)

    from app.tasks.trading_tasks import evaluate_strategy_task
    task = evaluate_strategy_task.apply_async(args=[strategy_id], queue="trading")

    return {
        "message": "AI 실행 요청이 거절되었습니다.",
        "strategy_id": strategy_id,
        "task_id": task.id,
    }
