"""
RiskManager — 손절/익절/포지션 한도 관리
매매 전 리스크 조건을 확인하고, 오픈 포지션 모니터링을 담당한다.
"""
from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

EMERGENCY_FLAG_PREFIX = "emergency:stop:"


class RiskManager:
    """
    거래 실행 전 리스크 체크 및 포지션 관리

    체크 항목:
    - 긴급 정지 플래그 (Redis)
    - 전략별 일일 최대 손실 한도
    - 심볼별 최대 포지션 수
    - 최소 잔고 확인
    """

    def __init__(self, redis_client, settings):
        self.redis = redis_client
        self.settings = settings
        # 기본 리스크 파라미터
        self.max_daily_loss_pct: float = getattr(settings, "MAX_DAILY_LOSS_PCT", 5.0)
        self.max_positions_per_symbol: int = getattr(settings, "MAX_POSITIONS_PER_SYMBOL", 3)
        self.min_balance_usdt: float = getattr(settings, "MIN_BALANCE_USDT", 10.0)

    # ------------------------------------------------------------------ #
    # 공개 메서드
    # ------------------------------------------------------------------ #

    async def can_trade(self, strategy_id: str) -> tuple[bool, str]:
        """
        거래 가능 여부 확인
        Returns:
            (True, "") — 거래 가능
            (False, reason) — 거래 불가 이유
        """
        # 1) 긴급 정지 플래그
        flag_key = f"{EMERGENCY_FLAG_PREFIX}{strategy_id}"
        reason = await self.redis.get(flag_key)
        if reason:
            reason_str = reason.decode() if isinstance(reason, bytes) else reason
            return False, f"긴급 정지 중: {reason_str}"

        # 2) 글로벌 긴급 정지
        global_stop = await self.redis.get("emergency:stop:global")
        if global_stop:
            return False, "전체 긴급 정지 중"

        return True, ""

    async def set_emergency_stop(
        self,
        strategy_id: str,
        reason: str,
        ttl_seconds: int = 3600,
    ) -> None:
        """긴급 정지 플래그 설정 (Redis TTL 포함)"""
        flag_key = f"{EMERGENCY_FLAG_PREFIX}{strategy_id}"
        await self.redis.setex(flag_key, ttl_seconds, reason)
        logger.warning("긴급 정지 플래그 설정: strategy=%s reason=%s", strategy_id, reason)

    async def clear_emergency_stop(self, strategy_id: str) -> None:
        """긴급 정지 해제"""
        flag_key = f"{EMERGENCY_FLAG_PREFIX}{strategy_id}"
        await self.redis.delete(flag_key)
        logger.info("긴급 정지 해제: strategy=%s", strategy_id)

    def calculate_order_quantity(
        self,
        order_config: dict,
        available_balance: Decimal,
        current_price: Decimal,
    ) -> Decimal:
        """
        주문 수량 계산
        quantity_type:
            - balance_pct: 잔고 비율 (%)
            - fixed_amount: USDT 고정 금액
            - fixed_qty: 코인 고정 수량
        """
        qty_type = order_config.get("quantity_type", "balance_pct")
        qty_value = Decimal(str(order_config.get("quantity_value", 10)))

        if qty_type == "balance_pct":
            amount_usdt = available_balance * qty_value / Decimal("100")
            if current_price > 0:
                return (amount_usdt / current_price).quantize(Decimal("0.00001"))
            return Decimal("0")

        elif qty_type == "fixed_amount":
            # qty_value = USDT 금액
            if current_price > 0:
                return (qty_value / current_price).quantize(Decimal("0.00001"))
            return Decimal("0")

        elif qty_type == "fixed_qty":
            return qty_value.quantize(Decimal("0.00001"))

        return Decimal("0")

    def validate_min_balance(self, balance_usdt: Decimal) -> bool:
        """최소 잔고 이상인지 확인"""
        return float(balance_usdt) >= self.min_balance_usdt

    async def record_daily_pnl(
        self,
        strategy_id: str,
        pnl_usdt: float,
    ) -> float:
        """일별 손익 누적 기록 (Redis)"""
        from datetime import date
        today = date.today().isoformat()
        key = f"pnl:daily:{strategy_id}:{today}"
        new_pnl = await self.redis.incrbyfloat(key, pnl_usdt)
        await self.redis.expire(key, 86400 * 2)  # 2일 TTL
        return new_pnl

    async def is_daily_loss_exceeded(self, strategy_id: str, balance_usdt: float) -> bool:
        """일일 최대 손실 한도 초과 여부"""
        from datetime import date
        today = date.today().isoformat()
        key = f"pnl:daily:{strategy_id}:{today}"
        raw = await self.redis.get(key)
        if not raw:
            return False
        pnl = float(raw)
        loss_limit = -abs(balance_usdt * self.max_daily_loss_pct / 100)
        return pnl <= loss_limit
