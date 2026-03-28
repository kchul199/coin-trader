"""
Backtest Celery Tasks
- run_backtest_task: 백테스트 비동기 실행 후 결과 저장
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date

from celery import shared_task

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
    name="tasks.run_backtest",
    bind=True,
    max_retries=1,
    default_retry_delay=5,
    soft_time_limit=300,
    time_limit=360,
)
def run_backtest_task(
    self,
    backtest_result_id: str,
    strategy_id: str,
    user_id: str,
    start_date_str: str,
    end_date_str: str,
    initial_capital: float,
    commission_pct: float,
    slippage_pct: float,
) -> dict:
    """백테스트 실행 Celery 태스크"""
    return _run_async(
        _run_backtest_async(
            backtest_result_id=backtest_result_id,
            strategy_id=strategy_id,
            user_id=user_id,
            start_date_str=start_date_str,
            end_date_str=end_date_str,
            initial_capital=initial_capital,
            commission_pct=commission_pct,
            slippage_pct=slippage_pct,
        )
    )


async def _run_backtest_async(
    backtest_result_id: str,
    strategy_id: str,
    user_id: str,
    start_date_str: str,
    end_date_str: str,
    initial_capital: float,
    commission_pct: float,
    slippage_pct: float,
) -> dict:
    """실제 백테스트 비동기 실행"""
    import redis.asyncio as aioredis
    from app.core.config import settings
    from app.core.database import async_session_factory
    from app.services.backtest_service import BacktestService

    start_date = date.fromisoformat(start_date_str)
    end_date = date.fromisoformat(end_date_str)

    redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

    try:
        # 상태: running
        await redis_client.hset(
            f"backtest:{backtest_result_id}",
            mapping={"status": "running", "progress": "0"},
        )
        await redis_client.expire(f"backtest:{backtest_result_id}", 3600)

        async with async_session_factory() as db:
            service = BacktestService(db)
            result = await service.run(
                strategy_id=strategy_id,
                user_id=user_id,
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
                commission_pct=commission_pct,
                slippage_pct=slippage_pct,
            )

        # 상태: completed
        await redis_client.hset(
            f"backtest:{backtest_result_id}",
            mapping={
                "status": "completed",
                "result_id": str(result.id),
                "total_return_pct": str(float(result.total_return_pct)),
            },
        )
        return {"status": "completed", "result_id": str(result.id)}

    except Exception as exc:
        logger.exception("Backtest failed: %s", backtest_result_id)
        await redis_client.hset(
            f"backtest:{backtest_result_id}",
            mapping={"status": "failed", "error": str(exc)},
        )
        return {"status": "failed", "error": str(exc)}

    finally:
        await redis_client.aclose()
