"""
OrderWatcher — 보유 포지션의 SL/TP/트레일링 스탑 감시

Redis에 캐시된 현재가를 우선 사용하고, 필요 시 거래소 API로 폴백한다.
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exchange.symbols import normalize_symbol
from app.models.strategy import Strategy
from app.trading.engine import TradingEngine

logger = logging.getLogger(__name__)


class OrderWatcher:
    def __init__(self, db: AsyncSession, redis_client, exchange, ws_manager, settings):
        self.db = db
        self.engine = TradingEngine(
            db=db,
            redis_client=redis_client,
            exchange=exchange,
            ws_manager=ws_manager,
            settings=settings,
        )

    async def watch_active_positions(self) -> dict:
        return await self._watch_strategies(
            select(Strategy).where(Strategy.is_active.is_(True))
        )

    async def watch_symbol_positions(self, symbol: str) -> dict:
        normalized_symbol = normalize_symbol(symbol, self.engine.settings.QUOTE_CURRENCY)
        return await self._watch_strategies(
            select(Strategy).where(
                Strategy.is_active.is_(True),
                Strategy.symbol == normalized_symbol,
            )
        )

    async def _watch_strategies(self, stmt) -> dict:
        result = await self.db.execute(
            stmt
        )
        strategies = result.scalars().all()

        watched = 0
        exited = 0
        skipped = 0
        failed = 0

        for strategy in strategies:
            order_config = strategy.order_config or {}
            if order_config.get("side", "buy") != "buy":
                continue

            if not self._has_exit_rule(order_config, strategy.exit_condition):
                continue

            watched += 1
            try:
                outcome = await self.engine.monitor_position(str(strategy.id))
            except Exception as exc:
                logger.error("포지션 감시 실패: strategy=%s error=%s", strategy.id, exc)
                failed += 1
                continue

            result_name = outcome.get("result")
            if result_name == "position_exit":
                exited += 1
            else:
                skipped += 1

        return {
            "watched": watched,
            "exited": exited,
            "skipped": skipped,
            "failed": failed,
        }

    @staticmethod
    def _has_exit_rule(order_config: dict, exit_condition: dict | None) -> bool:
        return bool(
            exit_condition
            or order_config.get("stop_loss_pct")
            or order_config.get("take_profit_pct")
            or order_config.get("trailing_stop")
        )
