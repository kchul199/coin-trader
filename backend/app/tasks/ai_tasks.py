"""
AI Celery Tasks — AI 자문 갱신
- refresh_all_ai_advice: 5분마다 활성 전략의 AI 자문 사전 갱신
"""
from __future__ import annotations

import asyncio
import logging

from celery import shared_task
from sqlalchemy import select

logger = logging.getLogger(__name__)


def _run_async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


@shared_task(
    name="tasks.refresh_ai_advice",
    bind=True,
    soft_time_limit=60,
    time_limit=90,
)
def refresh_ai_advice_task(self, strategy_id: str):
    """단일 전략 AI 자문 갱신"""
    async def _run():
        from app.database import AsyncSessionLocal
        from app.core.redis_client import get_redis
        from app.exchange.ccxt_adapter import create_exchange_adapter
        from app.config import settings
        from app.models.strategy import Strategy
        from app.trading.ai_consultant import AIConsultant

        redis = await get_redis()
        exchange = await create_exchange_adapter(settings)

        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Strategy).where(
                        Strategy.id == strategy_id,
                        Strategy.is_active.is_(True),
                        Strategy.ai_mode != "off",
                    )
                )
                strategy = result.scalar_one_or_none()
                if not strategy:
                    return {"skipped": True}

                # 현재 가격 조회
                import json
                from decimal import Decimal
                cache_key = f"price:{settings.EXCHANGE_ID}:{strategy.symbol}"
                raw = await redis.get(cache_key)
                current_price = Decimal("0")
                if raw:
                    try:
                        data = json.loads(raw)
                        current_price = Decimal(str(data.get("price") or data.get("last") or 0))
                    except Exception:
                        pass

                if current_price == 0:
                    try:
                        ticker = await exchange.get_ticker(strategy.symbol)
                        current_price = Decimal(str(ticker.get("last") or 0))
                    except Exception:
                        pass

                # OHLCV 로드
                ohlcv = await exchange.get_ohlcv(strategy.symbol, strategy.timeframe, limit=100)
                import pandas as pd
                ohlcv_df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
                ohlcv_df["close"] = ohlcv_df["close"].astype(float)
                ohlcv_df["volume"] = ohlcv_df["volume"].astype(float)

                # 지표 계산
                indicators = {}
                try:
                    import ta
                    close = ohlcv_df["close"]
                    rsi = ta.momentum.rsi(close, 14)
                    indicators["RSI_14"] = round(float(rsi.iloc[-1]), 2)
                    indicators["MA20"] = round(float(close.rolling(20).mean().iloc[-1]), 2)
                    indicators["MA50"] = round(float(close.rolling(50).mean().iloc[-1]), 2)
                    volume = ohlcv_df["volume"]
                    indicators["VOLUME"] = round(float(volume.iloc[-1]), 2)
                    indicators["VOLUME_MA20"] = round(float(volume.rolling(20).mean().iloc[-1]), 2)
                except Exception:
                    pass

                market_ctx = {
                    "symbol": strategy.symbol,
                    "price": str(current_price),
                    "quote_currency": settings.QUOTE_CURRENCY,
                    "change_24h": 0,
                    "indicators": indicators,
                    "recent_trades": [],
                    "btc_dominance": "N/A",
                    "market_trend": "N/A",
                    "volume_24h": "N/A",
                }

                consultant = AIConsultant(redis, settings)
                strategy_dict = {
                    "id": str(strategy.id),
                    "name": strategy.name,
                    "symbol": strategy.symbol,
                    "timeframe": strategy.timeframe,
                    "ai_mode": strategy.ai_mode,
                }
                result_data = await consultant.refresh_advice(strategy_dict, market_ctx)
                logger.info(
                    "AI 자문 갱신 완료: strategy=%s decision=%s",
                    strategy_id,
                    result_data.get("decision") if result_data else "none",
                )
                return result_data or {}
        finally:
            await exchange.close()

    return _run_async(_run())


@shared_task(name="tasks.refresh_all_ai_advice")
def refresh_all_ai_advice():
    """AI 모드가 켜진 활성 전략 전체 자문 갱신 (5분 주기)"""
    async def _fetch():
        from app.database import AsyncSessionLocal
        from app.models.strategy import Strategy

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Strategy.id).where(
                    Strategy.is_active.is_(True),
                    Strategy.ai_mode != "off",
                )
            )
            return [str(row[0]) for row in result.fetchall()]

    ids = _run_async(_fetch())
    logger.info("AI 자문 갱신 대상: %d개", len(ids))
    for sid in ids:
        refresh_ai_advice_task.apply_async(args=[sid], queue="ai_advice")
    return {"dispatched": len(ids)}
