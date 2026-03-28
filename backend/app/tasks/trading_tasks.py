"""
Trading Celery Tasks — 전략 평가 사이클
- evaluate_all_active_strategies: 30초마다 모든 활성 전략 평가
- evaluate_hold_queue: 5분마다 hold 대기 전략 재평가
- emergency_stop_task: 긴급 정지 처리
"""
from __future__ import annotations

import asyncio
import json
import logging

from celery import shared_task
from sqlalchemy import select

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Celery 동기 컨텍스트에서 비동기 코루틴 실행"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


@shared_task(
    name="tasks.evaluate_strategy",
    bind=True,
    max_retries=2,
    default_retry_delay=10,
    soft_time_limit=25,
    time_limit=30,
)
def evaluate_strategy_task(self, strategy_id: str):
    """단일 전략 평가 태스크"""
    async def _run():
        from app.database import AsyncSessionLocal
        from app.core.redis_client import get_redis
        from app.exchange.ccxt_adapter import create_exchange_adapter
        from app.websocket.manager import ws_manager
        from app.config import settings
        from app.trading.engine import TradingEngine

        redis = await get_redis()
        exchange = create_exchange_adapter()

        try:
            async with AsyncSessionLocal() as db:
                engine = TradingEngine(
                    db=db,
                    redis_client=redis,
                    exchange=exchange,
                    ws_manager=ws_manager,
                    settings=settings,
                )
                result = await engine.run_cycle(strategy_id)
                logger.info(
                    "전략 평가 완료: strategy_id=%s result=%s",
                    strategy_id, result.get("result"),
                )
                return result
        except Exception as exc:
            logger.error("전략 평가 오류: strategy_id=%s error=%s", strategy_id, exc)
            raise self.retry(exc=exc)
        finally:
            await exchange.close()

    return _run_async(_run())


@shared_task(name="tasks.evaluate_all_active_strategies")
def evaluate_all_active_strategies():
    """모든 활성 전략 평가 트리거 (30초 주기)"""
    async def _fetch_and_dispatch():
        from app.database import AsyncSessionLocal
        from app.models.strategy import Strategy

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Strategy.id).where(Strategy.is_active.is_(True))
            )
            ids = [str(row[0]) for row in result.fetchall()]

        logger.info("활성 전략 %d개 평가 시작", len(ids))
        for strategy_id in ids:
            evaluate_strategy_task.apply_async(
                args=[strategy_id],
                queue="trading",
            )
        return {"dispatched": len(ids)}

    return _run_async(_fetch_and_dispatch())


@shared_task(name="tasks.evaluate_hold_queue")
def evaluate_hold_queue():
    """Hold 대기 중인 전략 재평가 (5분 주기)"""
    async def _run():
        from app.core.redis_client import get_redis
        from app.models.strategy import Strategy
        from app.database import AsyncSessionLocal

        redis = await get_redis()

        # hold_retry:* 키 전체 스캔
        cursor = 0
        strategy_ids = []
        async for key in redis.scan_iter("hold_retry:*"):
            key_str = key.decode() if isinstance(key, bytes) else key
            strategy_id = key_str.replace("hold_retry:", "")
            count_raw = await redis.get(key)
            count = int(count_raw) if count_raw else 0

            # max_retry 확인
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Strategy).where(Strategy.id == strategy_id)
                )
                strategy = result.scalar_one_or_none()
                max_retry = strategy.hold_max_retry if strategy else 3

            if count < max_retry:
                strategy_ids.append(strategy_id)
            else:
                await redis.delete(key)
                logger.info("Hold 재시도 초과, 큐 제거: strategy=%s count=%d", strategy_id, count)

        for strategy_id in strategy_ids:
            evaluate_strategy_task.apply_async(
                args=[strategy_id],
                queue="trading",
            )

        return {"hold_queue_dispatched": len(strategy_ids)}

    return _run_async(_run())


@shared_task(name="tasks.emergency_stop")
def emergency_stop_task(strategy_id: str, user_id: str, reason: str):
    """긴급 정지 처리 태스크"""
    async def _run():
        from app.database import AsyncSessionLocal
        from app.core.redis_client import get_redis
        from app.exchange.ccxt_adapter import create_exchange_adapter
        from app.websocket.manager import ws_manager
        from app.config import settings
        from app.models.strategy import Strategy
        from app.models.order import Order
        from app.models.emergency_stop import EmergencyStop
        from sqlalchemy import update as sql_update
        import uuid

        redis = await get_redis()
        exchange = create_exchange_adapter()

        lock_key = f"emergency:lock:{strategy_id}"
        flag_key = f"emergency:stop:{strategy_id}"

        # 분산 락 획득 (원자적 SET NX EX)
        acquired = await redis.set(lock_key, user_id, nx=True, ex=5)
        if not acquired:
            return {"status": "already_stopping"}

        try:
            async with AsyncSessionLocal() as db:
                # DB 전략 비활성화
                await db.execute(
                    sql_update(Strategy)
                    .where(Strategy.id == strategy_id)
                    .values(is_active=False)
                )
                await db.commit()

                # Redis 긴급 정지 플래그 (1시간 TTL)
                await redis.setex(flag_key, 3600, reason)

                # 미체결 주문 조회
                result = await db.execute(
                    select(Order).where(
                        Order.strategy_id == strategy_id,
                        Order.status.in_(["open", "pending"]),
                    )
                )
                open_orders = result.scalars().all()

                # 병렬 취소
                cancel_results = await asyncio.gather(
                    *[
                        exchange.cancel_order(o.exchange_order_id, o.symbol)
                        for o in open_orders
                        if o.exchange_order_id
                    ],
                    return_exceptions=True,
                )

                # DB 상태 업데이트
                order_ids = [str(o.id) for o in open_orders]
                if order_ids:
                    await db.execute(
                        sql_update(Order)
                        .where(Order.id.in_(order_ids))
                        .values(status="cancelled")
                    )
                    await db.commit()

                # 긴급 정지 이력 저장
                stop_record = EmergencyStop(
                    strategy_id=strategy_id,
                    user_id=user_id,
                    reason=reason,
                    cancelled_orders=order_ids,
                )
                db.add(stop_record)
                await db.commit()

                # WebSocket 알림
                await ws_manager.broadcast_json({
                    "type": "emergency_stop",
                    "strategy_id": strategy_id,
                    "reason": reason,
                    "cancelled_orders": len(open_orders),
                })

                logger.warning(
                    "긴급 정지 완료: strategy=%s user=%s reason=%s cancelled=%d",
                    strategy_id, user_id, reason, len(open_orders),
                )
                return {"status": "stopped", "cancelled_orders": len(open_orders)}

        finally:
            await redis.delete(lock_key)
            await exchange.close()

    return _run_async(_run())
