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

from app.exchange.upbit_rules import UPBIT_KRW_MIN_ORDER_AMOUNT

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
        default_min_balance = 10000.0 if getattr(settings, "QUOTE_CURRENCY", "USDT") == "KRW" else 10.0
        self.min_quote_balance: float = getattr(
            settings,
            "MIN_QUOTE_BALANCE",
            getattr(settings, "MIN_BALANCE_USDT", default_min_balance),
        )

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
            - fixed_amount: 호가 통화 고정 금액
            - fixed_qty: 코인 고정 수량
        """
        qty_type = order_config.get("quantity_type", "balance_pct")
        if qty_type == "fixed_usdt":
            qty_type = "fixed_amount"
        qty_value = Decimal(str(order_config.get("quantity_value", 10)))

        if qty_type == "balance_pct":
            amount_quote = available_balance * qty_value / Decimal("100")
            if current_price > 0:
                return (amount_quote / current_price).quantize(Decimal("0.00001"))
            return Decimal("0")

        elif qty_type == "fixed_amount":
            # qty_value = 호가 통화 금액
            if current_price > 0:
                return (qty_value / current_price).quantize(Decimal("0.00001"))
            return Decimal("0")

        elif qty_type == "fixed_qty":
            return qty_value.quantize(Decimal("0.00001"))

        return Decimal("0")

    def calculate_sell_quantity(
        self,
        order_config: dict,
        held_quantity: Decimal,
        current_price: Decimal,
    ) -> Decimal:
        """매도 주문 수량 계산"""
        qty_type = order_config.get("quantity_type", "balance_pct")
        if qty_type == "fixed_usdt":
            qty_type = "fixed_amount"
        qty_value = Decimal(str(order_config.get("quantity_value", 10)))

        if qty_type == "balance_pct":
            requested_qty = held_quantity * qty_value / Decimal("100")
            return min(held_quantity, requested_qty).quantize(Decimal("0.00001"))

        if qty_type == "fixed_amount":
            if current_price > 0:
                requested_qty = qty_value / current_price
                return min(held_quantity, requested_qty).quantize(Decimal("0.00001"))
            return Decimal("0")

        if qty_type == "fixed_qty":
            return min(held_quantity, qty_value).quantize(Decimal("0.00001"))

        return held_quantity.quantize(Decimal("0.00001"))

    def build_split_quantities(
        self,
        total_quantity: Decimal,
        split_count: int,
        current_price: Decimal,
    ) -> list[Decimal]:
        """총 주문 수량을 균등 분할한다."""
        normalized_count = max(1, int(split_count or 1))
        total_quantity = total_quantity.quantize(Decimal("0.00001"))
        if total_quantity <= 0:
            return []

        min_notional = Decimal("0")
        if (
            getattr(self.settings, "EXCHANGE_ID", "") == "upbit"
            and getattr(self.settings, "QUOTE_CURRENCY", "") == "KRW"
        ):
            min_notional = UPBIT_KRW_MIN_ORDER_AMOUNT

        if min_notional > 0 and current_price > 0:
            max_splits = int((total_quantity * current_price) // min_notional)
            normalized_count = max(1, min(normalized_count, max_splits or 1))

        base_quantity = (total_quantity / Decimal(str(normalized_count))).quantize(Decimal("0.00001"))
        quantities: list[Decimal] = []
        assigned = Decimal("0")

        for index in range(normalized_count):
            if index == normalized_count - 1:
                tranche = (total_quantity - assigned).quantize(Decimal("0.00001"))
            else:
                tranche = base_quantity
                assigned += tranche

            if tranche > 0:
                quantities.append(tranche)

        return quantities or [total_quantity]

    def validate_min_balance(self, balance_usdt: Decimal) -> bool:
        """최소 잔고 이상인지 확인"""
        return float(balance_usdt) >= self.min_quote_balance

    def validate_order_notional(self, quantity: Decimal, current_price: Decimal) -> tuple[bool, Decimal]:
        """거래소 최소 주문 금액 충족 여부"""
        notional = quantity * current_price

        if (
            getattr(self.settings, "EXCHANGE_ID", "") == "upbit"
            and getattr(self.settings, "QUOTE_CURRENCY", "") == "KRW"
        ):
            return notional >= UPBIT_KRW_MIN_ORDER_AMOUNT, UPBIT_KRW_MIN_ORDER_AMOUNT

        return True, Decimal("0")

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
