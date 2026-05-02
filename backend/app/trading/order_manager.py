"""
OrderManager — 주문 실행 및 상태 관리
거래소 주문 생성/취소, DB 저장, WebSocket 알림을 담당한다.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.balance import Balance
from app.models.order import Order
from app.models.portfolio import Portfolio
from app.models.strategy import Strategy
from app.exchange.symbols import split_symbol
from app.trading.risk_manager import RiskManager

logger = logging.getLogger(__name__)


class OrderManager:
    """
    주문 실행 흐름:
    1. DB에 pending 상태 주문 레코드 생성
    2. 거래소 API 호출 (ccxt_adapter)
    3. 성공 시 DB 업데이트 (open 상태 + exchange_order_id)
    4. WebSocket으로 order_created 이벤트 브로드캐스트
    5. 실패 시 DB 업데이트 (rejected 상태) + 로깅
    """

    def __init__(self, exchange_adapter, ws_manager, db_session: AsyncSession, redis_client=None, settings=None):
        self.exchange = exchange_adapter
        self.ws = ws_manager
        self.db = db_session
        self.redis = redis_client
        self.settings = settings
        self.risk_manager = RiskManager(redis_client, settings) if redis_client and settings else None

    async def place_order(
        self,
        strategy_id: str,
        exchange_id: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        quote_amount: Optional[Decimal] = None,
        order_config: Optional[dict] = None,
    ) -> dict:
        """
        주문 실행
        Returns: {"success": bool, "order_id": str, "exchange_order_id": str, "error": str}
        """
        order_id = str(uuid.uuid4())
        order_config = order_config or {}
        reservation = None

        # 1) DB에 pending 상태 저장
        db_order = Order(
            id=order_id,
            strategy_id=strategy_id,
            exchange_id=exchange_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=float(quantity),
            price=float(price) if price else None,
            status="pending",
        )
        self.db.add(db_order)
        await self.db.flush()  # ID 확정

        try:
            reservation = await self._reserve_balance_for_order(
                order_id=order_id,
                strategy_id=strategy_id,
                exchange_id=exchange_id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=price,
                quote_amount=quote_amount,
            )

            # 2) 거래소 API 호출
            ex_result = await self.exchange.place_order(
                symbol=symbol,
                order_type=order_type,
                side=side,
                amount=float(quantity),
                price=float(price) if price else None,
                quote_amount=float(quote_amount) if quote_amount is not None else None,
            )

            exchange_order_id = ex_result.get("id", "")
            ex_status = ex_result.get("status", "open")
            mapped_status = self._map_exchange_status(ex_status)
            filled_qty = ex_result.get("filled") or float(quantity)
            avg_price = ex_result.get("average") or ex_result.get("price") or (float(price) if price else None)
            fee_info = ex_result.get("fee") or {}
            fee = fee_info.get("cost", 0)

            # 3) DB 업데이트 (open)
            db_order.exchange_order_id = exchange_order_id
            db_order.status = mapped_status
            db_order.filled_quantity = filled_qty if mapped_status == "filled" else (db_order.filled_quantity or 0)
            db_order.avg_fill_price = avg_price if avg_price is not None else db_order.avg_fill_price
            db_order.fee = fee if fee is not None else db_order.fee
            db_order.filled_at = datetime.now(timezone.utc) if mapped_status == "filled" else db_order.filled_at
            db_order.updated_at = datetime.now(timezone.utc)
            await self.db.commit()

            if mapped_status == "filled":
                await self._apply_filled_order_effects(db_order)
                await self._reconcile_balance_reservation(db_order, mapped_status)

            # 4) WebSocket 알림
            await self.ws.broadcast_json({
                "type": "order_created",
                "order_id": order_id,
                "strategy_id": strategy_id,
                "symbol": symbol,
                "side": side,
                "quantity": str(quantity),
                "status": db_order.status,
            })

            if mapped_status == "filled":
                await self.ws.broadcast_json({
                    "type": "order_filled",
                    "order_id": order_id,
                    "strategy_id": strategy_id,
                    "symbol": symbol,
                    "side": side,
                    "filled_quantity": str(db_order.filled_quantity or quantity),
                    "avg_fill_price": str(db_order.avg_fill_price or avg_price or ""),
                })

            logger.info(
                "주문 생성 성공: order_id=%s exchange_id=%s symbol=%s side=%s qty=%s",
                order_id, exchange_order_id, symbol, side, quantity,
            )
            return {
                "success": True,
                "order_id": order_id,
                "exchange_order_id": exchange_order_id,
                "status": db_order.status,
            }

        except Exception as exc:
            # 5) 실패 처리
            logger.error("주문 실패: order_id=%s error=%s", order_id, exc)
            db_order.status = "rejected"
            db_order.updated_at = datetime.now(timezone.utc)
            await self.db.commit()
            if reservation is not None:
                await self._reconcile_balance_reservation(db_order, "rejected")

            await self.ws.broadcast_json({
                "type": "order_failed",
                "order_id": order_id,
                "strategy_id": strategy_id,
                "symbol": symbol,
                "error": str(exc),
            })
            return {"success": False, "order_id": order_id, "error": str(exc)}

    async def cancel_order(
        self,
        order_id: str,
        exchange_order_id: str,
        symbol: str,
    ) -> bool:
        """주문 취소"""
        try:
            order_result = await self.db.execute(
                select(Order).where(Order.id == order_id)
            )
            order = order_result.scalar_one_or_none()

            await self.exchange.cancel_order(exchange_order_id, symbol)
            await self.db.execute(
                update(Order)
                .where(Order.id == order_id)
                .values(status="cancelled", updated_at=datetime.now(timezone.utc))
            )
            await self.db.commit()
            if order is not None:
                order.status = "cancelled"
                await self._reconcile_balance_reservation(order, "cancelled")
            logger.info("주문 취소 완료: order_id=%s", order_id)
            return True
        except Exception as exc:
            logger.error("주문 취소 실패: order_id=%s error=%s", order_id, exc)
            return False

    async def sync_order_status(self, order: Order) -> str:
        """거래소에서 주문 상태 동기화"""
        try:
            previous_status = order.status
            ex_order = await self.exchange.exchange.fetch_order(
                order.exchange_order_id, order.symbol
            )
            new_status = ex_order.get("status", order.status)
            filled_qty = ex_order.get("filled", order.filled_quantity or 0)
            avg_price = ex_order.get("average") or ex_order.get("price")
            fee = ex_order.get("fee", {}).get("cost", 0)

            mapped_status = self._map_exchange_status(new_status)

            await self.db.execute(
                update(Order)
                .where(Order.id == str(order.id))
                .values(
                    status=mapped_status,
                    filled_quantity=filled_qty,
                    avg_fill_price=avg_price,
                    fee=fee,
                    filled_at=datetime.now(timezone.utc) if mapped_status == "filled" else None,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await self.db.commit()

            order.status = mapped_status
            order.filled_quantity = filled_qty
            order.avg_fill_price = avg_price
            order.fee = fee
            order.filled_at = datetime.now(timezone.utc) if mapped_status == "filled" else order.filled_at

            if mapped_status == "filled":
                if previous_status != "filled":
                    await self._apply_filled_order_effects(order)
                await self._reconcile_balance_reservation(order, mapped_status)
                await self.ws.broadcast_json({
                    "type": "order_filled",
                    "order_id": str(order.id),
                    "strategy_id": str(order.strategy_id),
                    "symbol": order.symbol,
                    "side": order.side,
                    "filled_quantity": filled_qty,
                    "avg_fill_price": str(avg_price),
                })
            elif mapped_status in {"cancelled", "rejected"}:
                await self._reconcile_balance_reservation(order, mapped_status)

            return mapped_status

        except Exception as exc:
            logger.warning("주문 상태 동기화 실패: order_id=%s error=%s", order.id, exc)
            return order.status

    def _map_exchange_status(self, status: str) -> str:
        status_map = {
            "closed": "filled",
            "filled": "filled",
            "open": "open",
            "canceled": "cancelled",
            "cancelled": "cancelled",
            "expired": "cancelled",
        }
        return status_map.get(status, status or "open")

    async def _reserve_balance_for_order(
        self,
        order_id: str,
        strategy_id: str,
        exchange_id: str,
        symbol: str,
        side: str,
        quantity: Decimal,
        price: Optional[Decimal],
        quote_amount: Optional[Decimal],
    ) -> Optional[dict]:
        if self.redis is None:
            return None

        strategy = await self.db.get(Strategy, uuid.UUID(strategy_id))
        if not strategy:
            raise ValueError("전략을 찾을 수 없습니다.")

        base_asset, quote_asset = split_symbol(symbol, self.settings.QUOTE_CURRENCY)
        if side == "buy":
            reserve_symbol = quote_asset
            reserve_amount = Decimal(str(quote_amount or 0))
            if reserve_amount <= 0 and price is not None:
                reserve_amount = Decimal(str(price)) * Decimal(str(quantity))
            if reserve_amount <= 0 and self.exchange is not None:
                ticker = await self.exchange.get_ticker(symbol)
                market_price = Decimal(str(ticker.get("last") or ticker.get("close") or 0))
                if market_price > 0:
                    reserve_amount = market_price * Decimal(str(quantity))
            if reserve_amount <= 0:
                raise ValueError("매수 주문 예약 금액을 계산할 수 없습니다.")
        else:
            reserve_symbol = base_asset
            reserve_amount = Decimal(str(quantity))

        if reserve_amount <= 0:
            raise ValueError("예약할 잔고 수량이 0 이하입니다.")

        user_id = str(strategy.user_id)
        lock_key = self._balance_lock_key(exchange_id, user_id, reserve_symbol)
        acquired = await self._acquire_lock(lock_key)
        if not acquired:
            raise RuntimeError("잔고 예약 처리 중입니다. 잠시 후 다시 시도해주세요.")

        try:
            shadow_key = self._balance_shadow_key(exchange_id, user_id, reserve_symbol)
            reserved_key = self._balance_reserved_key(exchange_id, user_id, reserve_symbol)

            raw_shadow = await self.redis.get(shadow_key)
            if raw_shadow is None:
                initial_balance = await self._load_initial_reservation_balance(
                    strategy=strategy,
                    exchange_id=exchange_id,
                    reserve_symbol=reserve_symbol,
                )
                await self.redis.setex(
                    shadow_key,
                    int(getattr(self.settings, "BALANCE_RESERVATION_TTL_SECONDS", 3600)),
                    str(initial_balance),
                )
                shadow_balance = initial_balance
            else:
                shadow_balance = Decimal(str(raw_shadow))

            if shadow_balance < reserve_amount:
                raise RuntimeError(
                    f"가용 잔고 선점 실패: {reserve_symbol} {shadow_balance} < {reserve_amount}"
                )

            await self.redis.incrbyfloat(shadow_key, float(-reserve_amount))
            await self.redis.incrbyfloat(reserved_key, float(reserve_amount))
            ttl = int(getattr(self.settings, "BALANCE_RESERVATION_TTL_SECONDS", 3600))
            await self.redis.expire(shadow_key, ttl)
            await self.redis.expire(reserved_key, ttl)

            reservation = {
                "exchange_id": exchange_id,
                "user_id": user_id,
                "reserve_symbol": reserve_symbol,
                "reserve_amount": str(reserve_amount),
                "side": side,
                "base_asset": base_asset,
                "quote_asset": quote_asset,
            }
            await self.redis.setex(
                self._order_reservation_key(order_id),
                ttl,
                json.dumps(reservation, ensure_ascii=False),
            )
            return reservation
        finally:
            await self.redis.delete(lock_key)

    async def _reconcile_balance_reservation(self, order: Order, final_status: str) -> None:
        if self.redis is None or final_status not in {"filled", "cancelled", "rejected"}:
            return

        reservation_key = self._order_reservation_key(str(order.id))
        raw = await self.redis.get(reservation_key)
        if not raw:
            return

        reservation = json.loads(raw)
        exchange_id = reservation["exchange_id"]
        user_id = reservation["user_id"]
        reserve_symbol = reservation["reserve_symbol"]
        reserve_amount = Decimal(str(reservation["reserve_amount"]))
        lock_key = self._balance_lock_key(exchange_id, user_id, reserve_symbol)

        acquired = await self._acquire_lock(lock_key)
        if not acquired:
            logger.warning("예약 잔고 정리 잠금 획득 실패: order_id=%s", order.id)
            return

        try:
            shadow_key = self._balance_shadow_key(exchange_id, user_id, reserve_symbol)
            reserved_key = self._balance_reserved_key(exchange_id, user_id, reserve_symbol)

            if final_status in {"cancelled", "rejected"}:
                await self.redis.incrbyfloat(shadow_key, float(reserve_amount))
            await self.redis.incrbyfloat(reserved_key, float(-reserve_amount))

            if final_status == "filled":
                await self._credit_post_fill_shadow_balance(order, reservation)

            await self.redis.delete(reservation_key)
        finally:
            await self.redis.delete(lock_key)

    async def _credit_post_fill_shadow_balance(self, order: Order, reservation: dict) -> None:
        exchange_id = reservation["exchange_id"]
        user_id = reservation["user_id"]
        ttl = int(getattr(self.settings, "BALANCE_RESERVATION_TTL_SECONDS", 3600))
        qty = Decimal(str(order.filled_quantity or order.quantity or 0))
        fill_price = Decimal(str(order.avg_fill_price or order.price or 0))
        fee = Decimal(str(order.fee or 0))

        if order.side == "buy":
            if qty <= 0:
                return
            base_asset = reservation["base_asset"]
            base_shadow_key = self._balance_shadow_key(exchange_id, user_id, base_asset)
            await self._ensure_shadow_key(base_shadow_key, Decimal("0"), ttl)
            await self.redis.incrbyfloat(base_shadow_key, float(qty))
            await self.redis.expire(base_shadow_key, ttl)
            return

        if order.side != "sell" or qty <= 0 or fill_price <= 0:
            return

        quote_asset = reservation["quote_asset"]
        net_quote = (qty * fill_price) - fee
        if net_quote <= 0:
            return
        quote_shadow_key = self._balance_shadow_key(exchange_id, user_id, quote_asset)
        await self._ensure_shadow_key(quote_shadow_key, Decimal("0"), ttl)
        await self.redis.incrbyfloat(quote_shadow_key, float(net_quote))
        await self.redis.expire(quote_shadow_key, ttl)

    async def _load_initial_reservation_balance(
        self,
        strategy: Strategy,
        exchange_id: str,
        reserve_symbol: str,
    ) -> Decimal:
        balance_result = await self.db.execute(
            select(Balance).where(
                Balance.user_id == strategy.user_id,
                Balance.exchange_id == exchange_id,
                Balance.symbol == reserve_symbol,
            )
        )
        balance = balance_result.scalar_one_or_none()
        if balance is not None:
            return Decimal(str(balance.available or 0))

        base_asset, _ = split_symbol(strategy.symbol, self.settings.QUOTE_CURRENCY)
        if reserve_symbol == base_asset:
            portfolio_result = await self.db.execute(
                select(Portfolio).where(
                    Portfolio.user_id == strategy.user_id,
                    Portfolio.exchange_id == exchange_id,
                    Portfolio.symbol == strategy.symbol,
                )
            )
            portfolio = portfolio_result.scalar_one_or_none()
            if portfolio is not None:
                return Decimal(str(portfolio.quantity or 0))

        return Decimal("0")

    async def _ensure_shadow_key(self, key: str, default_value: Decimal, ttl: int) -> None:
        current = await self.redis.get(key)
        if current is None:
            await self.redis.setex(key, ttl, str(default_value))

    async def _acquire_lock(self, lock_key: str, retries: int = 3) -> bool:
        for attempt in range(retries):
            acquired = await self.redis.set(lock_key, "1", nx=True, ex=5)
            if acquired:
                return True
            await asyncio.sleep(0.2 * (attempt + 1))
        return False

    @staticmethod
    def _balance_shadow_key(exchange_id: str, user_id: str, symbol: str) -> str:
        return f"balance:shadow:{exchange_id}:{user_id}:{symbol}"

    @staticmethod
    def _balance_reserved_key(exchange_id: str, user_id: str, symbol: str) -> str:
        return f"balance:reserved:{exchange_id}:{user_id}:{symbol}"

    @staticmethod
    def _balance_lock_key(exchange_id: str, user_id: str, symbol: str) -> str:
        return f"balance:lock:{exchange_id}:{user_id}:{symbol}"

    @staticmethod
    def _order_reservation_key(order_id: str) -> str:
        return f"balance:reservation:order:{order_id}"

    async def _apply_filled_order_effects(self, order: Order) -> None:
        """체결 주문을 포트폴리오와 일일 손익에 반영한다."""
        strategy_result = await self.db.execute(
            select(Strategy).where(Strategy.id == order.strategy_id)
        )
        strategy = strategy_result.scalar_one_or_none()
        if not strategy:
            logger.warning("전략을 찾지 못해 체결 반영 스킵: order_id=%s", order.id)
            return

        qty = Decimal(str(order.filled_quantity or order.quantity or 0))
        fill_price = Decimal(str(order.avg_fill_price or order.price or 0))
        fee = Decimal(str(order.fee or 0))
        if qty <= 0 or fill_price <= 0:
            logger.warning("체결 수량/가격 부족으로 체결 반영 스킵: order_id=%s", order.id)
            return

        portfolio_result = await self.db.execute(
            select(Portfolio).where(
                Portfolio.user_id == strategy.user_id,
                Portfolio.exchange_id == order.exchange_id,
                Portfolio.symbol == order.symbol,
            )
        )
        portfolio = portfolio_result.scalar_one_or_none()

        if order.side == "buy":
            total_cost = qty * fill_price + fee
            if portfolio:
                prev_qty = Decimal(str(portfolio.quantity))
                prev_cost_basis = Decimal(str(portfolio.initial_capital))
                new_qty = prev_qty + qty
                new_cost_basis = prev_cost_basis + total_cost
                portfolio.quantity = new_qty
                portfolio.avg_buy_price = (new_cost_basis / new_qty) if new_qty > 0 else Decimal("0")
                portfolio.initial_capital = new_cost_basis
                portfolio.last_updated = datetime.now(timezone.utc)
            else:
                self.db.add(
                    Portfolio(
                        user_id=strategy.user_id,
                        symbol=order.symbol,
                        exchange_id=order.exchange_id,
                        quantity=qty,
                        avg_buy_price=(total_cost / qty),
                        initial_capital=total_cost,
                    )
                )
            await self.db.commit()
            return

        if order.side != "sell":
            return

        if not portfolio:
            logger.warning("포트폴리오가 없어 매도 체결 반영 스킵: order_id=%s", order.id)
            return

        prev_qty = Decimal(str(portfolio.quantity))
        avg_buy_price = Decimal(str(portfolio.avg_buy_price))
        sell_qty = min(prev_qty, qty)
        if sell_qty <= 0:
            return

        gross_proceeds = sell_qty * fill_price
        proportional_fee = fee * (sell_qty / qty) if qty > 0 else Decimal("0")
        realized_proceeds = gross_proceeds - proportional_fee
        realized_cost = avg_buy_price * sell_qty
        pnl = realized_proceeds - realized_cost
        remaining_qty = prev_qty - sell_qty

        if remaining_qty > 0:
            portfolio.quantity = remaining_qty
            portfolio.initial_capital = avg_buy_price * remaining_qty
            portfolio.last_updated = datetime.now(timezone.utc)
        else:
            await self.db.delete(portfolio)

        await self.db.commit()

        if self.risk_manager is not None:
            await self.risk_manager.record_daily_pnl(str(order.strategy_id), float(pnl))
