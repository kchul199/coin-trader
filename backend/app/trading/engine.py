"""
TradingEngine — 전략 평가 사이클 오케스트레이터

흐름:
  Celery Beat (30초) → evaluate_strategies_task
    → TradingEngine.run_cycle(strategy)
      1. RiskManager.can_trade()
      2. 현재 가격/지표 로드 (Redis 캐시 → ccxt)
      3. StrategyEvaluator.evaluate(condition_tree)
      4. [조건 미충족] → 종료
      5. [조건 충족]
           → 전략 충돌 감지
           → AI 자문 확인 (ai_mode)
           → OrderManager.place_order()
           → DB 저장 + WS Push
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

import pandas as pd
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.strategy import Strategy
from app.models.strategy_conflict import StrategyConflict
from app.models.ai_consultation import AIConsultation as AiConsultation
from app.models.balance import Balance
from app.models.order import Order
from app.models.portfolio import Portfolio
from app.trading.strategy_evaluator import StrategyEvaluator, ConditionResult
from app.trading.risk_manager import RiskManager
from app.trading.order_manager import OrderManager
from app.trading.ai_consultant import AIConsultant
from app.exchange.ccxt_adapter import CcxtAdapter
from app.exchange.symbols import to_compact_symbol
from app.websocket.manager import ConnectionManager

logger = logging.getLogger(__name__)


class TradingEngine:
    """
    단일 전략 사이클을 관리한다.
    인스턴스는 각 Celery 태스크 실행 시 생성된다.
    """

    def __init__(
        self,
        db: AsyncSession,
        redis_client,
        exchange: CcxtAdapter,
        ws_manager: ConnectionManager,
        settings,
    ):
        self.db = db
        self.redis = redis_client
        self.exchange = exchange
        self.ws = ws_manager
        self.settings = settings

        self.evaluator = StrategyEvaluator()
        self.risk_manager = RiskManager(redis_client, settings)
        self.order_manager = OrderManager(
            exchange,
            ws_manager,
            db,
            redis_client=redis_client,
            settings=settings,
        )
        self.ai_consultant = AIConsultant(redis_client, settings)

    # ------------------------------------------------------------------ #
    # 메인 사이클
    # ------------------------------------------------------------------ #

    async def run_cycle(self, strategy_id: str) -> dict:
        """
        전략 하나에 대한 전체 평가 → 주문 사이클 실행
        Returns: {"result": "skipped"|"no_signal"|"conflict"|"ai_hold"|"order_placed"|"order_failed", ...}
        """
        # 1) 전략 로드
        strategy = await self._load_strategy(strategy_id)
        if not strategy or not strategy.is_active:
            return {"result": "skipped", "reason": "전략 비활성 또는 없음"}

        strategy_dict = {
            "id": str(strategy.id),
            "user_id": str(strategy.user_id),
            "name": strategy.name,
            "symbol": strategy.symbol,
            "timeframe": strategy.timeframe,
            "ai_mode": strategy.ai_mode,
            "priority": strategy.priority,
            "condition_tree": strategy.condition_tree,
            "order_config": strategy.order_config,
            "hold_retry_interval": strategy.hold_retry_interval,
            "hold_max_retry": strategy.hold_max_retry,
            "exit_condition": strategy.exit_condition,
        }

        if await self._has_open_orders(strategy_id):
            return {"result": "skipped", "reason": "미체결 주문 대기 중"}

        # 2) 리스크 체크
        can_trade, stop_reason = await self.risk_manager.can_trade(strategy_id)
        if not can_trade:
            logger.info("거래 차단 (리스크): strategy=%s reason=%s", strategy_id, stop_reason)
            return {"result": "skipped", "reason": stop_reason}

        # 3) OHLCV 데이터 로드
        ohlcv_df = await self._load_ohlcv(strategy.symbol, strategy.timeframe)
        if ohlcv_df is None or ohlcv_df.empty:
            logger.warning("OHLCV 데이터 없음: strategy=%s symbol=%s", strategy_id, strategy.symbol)
            return {"result": "skipped", "reason": "OHLCV 데이터 없음"}

        # 4) 현재 가격 로드
        current_price = await self._get_current_price(strategy.symbol)
        if current_price is None:
            return {"result": "skipped", "reason": "현재 가격 조회 실패"}

        position = await self._get_portfolio_position(strategy)

        exit_result = await self._handle_position_exit(
            strategy,
            strategy_dict,
            position,
            current_price,
            ohlcv_df,
        )
        if exit_result is not None:
            return exit_result

        # 5) 조건 평가
        condition_result: ConditionResult = self.evaluator.evaluate(
            strategy.condition_tree, ohlcv_df
        )
        logger.debug(
            "조건 평가: strategy=%s matched=%s triggered=%s",
            strategy_id, condition_result.matched, condition_result.triggered,
        )

        if not condition_result.matched:
            return {"result": "no_signal", "triggered": condition_result.triggered}

        # 6) 전략 충돌 감지
        conflict = await self._check_conflicts(strategy_dict)
        if conflict:
            await self._record_conflict(strategy_dict, conflict)
            return {"result": "conflict", "conflict_strategies": conflict}

        # 7) AI 자문
        ai_decision = await self._consult_ai(strategy_dict, current_price, ohlcv_df)
        if ai_decision == "avoid":
            logger.info("AI 자문 회피: strategy=%s", strategy_id)
            return {"result": "ai_avoid", "ai_decision": ai_decision}

        if ai_decision == "pending_approval":
            return {"result": "ai_pending_approval", "ai_decision": ai_decision}

        if ai_decision == "hold":
            await self._enqueue_hold_retry(strategy_id)
            return {"result": "ai_hold", "ai_decision": ai_decision}

        # 8) 잔고 확인 및 수량 계산
        order_config = strategy_dict["order_config"]
        order_side = order_config.get("side", "buy")

        if order_side == "sell":
            held_quantity = Decimal(str(position.quantity or 0)) if position else Decimal("0")
            if held_quantity <= 0:
                return {"result": "skipped", "reason": "매도 가능한 보유 수량 없음"}
            quantity = self.risk_manager.calculate_sell_quantity(
                order_config,
                held_quantity,
                current_price,
            )
        else:
            balance = await self._get_available_balance(strategy, order_config)
            if balance is None or not self.risk_manager.validate_min_balance(balance):
                return {
                    "result": "skipped",
                    "reason": f"잔고 부족: {balance} {self.settings.QUOTE_CURRENCY}",
                }

            if await self.risk_manager.is_daily_loss_exceeded(strategy_id, float(balance)):
                reason = f"일일 손실 한도 초과 ({self.risk_manager.max_daily_loss_pct:.1f}%)"
                await self.risk_manager.set_emergency_stop(strategy_id, reason)
                return {"result": "skipped", "reason": reason}

            quantity = self.risk_manager.calculate_order_quantity(
                order_config,
                balance,
                current_price,
            )
        if quantity <= 0:
            return {"result": "skipped", "reason": "주문 수량 계산 오류"}

        is_valid_notional, min_notional = self.risk_manager.validate_order_notional(
            quantity,
            current_price,
        )
        order_notional = quantity * current_price
        if not is_valid_notional:
            return {
                "result": "skipped",
                "reason": (
                    f"최소 주문 금액 미달: {order_notional:.0f} {self.settings.QUOTE_CURRENCY} "
                    f"< {min_notional:.0f} {self.settings.QUOTE_CURRENCY}"
                ),
            }

        # 9) 주문 실행
        order_result = await self._place_split_orders(
            strategy_id=strategy_id,
            symbol=strategy.symbol,
            side=order_config.get("side", "buy"),
            order_type=order_config.get("type", "market"),
            quantity=quantity,
            current_price=current_price,
            order_config=order_config,
        )

        if order_result.get("success") and order_config.get("trailing_stop"):
            await self._set_trailing_peak(strategy_id, current_price)

        # 10) AI 자문 결과 DB 저장
        if ai_decision is not None:
            await self._save_ai_consultation(
                strategy_id=strategy_id,
                order_id=order_result.get("primary_order_id") if order_result["success"] else None,
            )

        return {
            "result": "order_placed" if order_result["success"] else "order_failed",
            "order": order_result,
            "triggered_conditions": condition_result.triggered,
        }

    async def monitor_position(self, strategy_id: str) -> dict:
        """보유 포지션의 익절/손절/트레일링 스탑 조건만 감시한다."""
        strategy = await self._load_strategy(strategy_id)
        if not strategy or not strategy.is_active:
            return {"result": "skipped", "reason": "전략 비활성 또는 없음"}

        order_config = strategy.order_config or {}
        if order_config.get("side", "buy") != "buy":
            return {"result": "skipped", "reason": "매수 전략 포지션 감시만 지원"}

        if await self._has_open_orders(strategy_id):
            return {"result": "skipped", "reason": "미체결 주문 대기 중"}

        can_trade, stop_reason = await self.risk_manager.can_trade(strategy_id)
        if not can_trade:
            return {"result": "skipped", "reason": stop_reason}

        position = await self._get_portfolio_position(strategy)
        if not position or Decimal(str(position.quantity or 0)) <= 0:
            await self._clear_trailing_peak(strategy_id)
            return {"result": "skipped", "reason": "감시 대상 포지션 없음"}

        strategy_dict = {
            "id": str(strategy.id),
            "user_id": str(strategy.user_id),
            "symbol": strategy.symbol,
            "timeframe": strategy.timeframe,
            "order_config": order_config,
            "exit_condition": strategy.exit_condition,
        }

        current_price = await self._get_current_price(strategy.symbol)
        if current_price is None:
            return {"result": "skipped", "reason": "현재 가격 조회 실패"}

        ohlcv_df = None
        if strategy.exit_condition:
            ohlcv_df = await self._load_ohlcv(strategy.symbol, strategy.timeframe)
            if ohlcv_df is None or ohlcv_df.empty:
                return {"result": "skipped", "reason": "청산용 OHLCV 데이터 없음"}

        exit_result = await self._handle_position_exit(
            strategy,
            strategy_dict,
            position,
            current_price,
            ohlcv_df,
        )
        if exit_result is not None:
            return exit_result

        return {"result": "skipped", "reason": "청산 조건 미충족"}

    # ------------------------------------------------------------------ #
    # 보조 메서드
    # ------------------------------------------------------------------ #

    async def _load_strategy(self, strategy_id: str) -> Optional[Strategy]:
        result = await self.db.execute(
            select(Strategy).where(Strategy.id == uuid.UUID(strategy_id))
        )
        return result.scalar_one_or_none()

    async def _has_open_orders(self, strategy_id: str) -> bool:
        result = await self.db.execute(
            select(Order.id).where(
                Order.strategy_id == uuid.UUID(strategy_id),
                Order.status.in_(["pending", "open"]),
            )
        )
        return result.first() is not None

    async def _load_ohlcv(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        try:
            ohlcv = await self.exchange.get_ohlcv(symbol, timeframe, limit=200)
            if not ohlcv:
                return None
            df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["close"] = df["close"].astype(float)
            df["volume"] = df["volume"].astype(float)
            return df
        except Exception as exc:
            logger.error("OHLCV 로드 실패: symbol=%s error=%s", symbol, exc)
            return None

    async def _get_current_price(self, symbol: str) -> Optional[Decimal]:
        """Redis 캐시 우선 → ccxt 폴백"""
        cache_key = f"price:{self.settings.EXCHANGE_ID}:{to_compact_symbol(symbol, self.settings.QUOTE_CURRENCY)}"
        raw = await self.redis.get(cache_key)
        if raw:
            try:
                data = json.loads(raw)
                if isinstance(data, dict):
                    price = data.get("price") or data.get("last") or data.get("close")
                else:
                    price = data
                return Decimal(str(price)) if price else None
            except Exception:
                try:
                    return Decimal(str(raw))
                except Exception:
                    pass

        try:
            ticker = await self.exchange.get_ticker(symbol)
            price = ticker.get("last") or ticker.get("close")
            return Decimal(str(price)) if price else None
        except Exception as exc:
            logger.error("현재가 조회 실패: symbol=%s error=%s", symbol, exc)
            return None

    async def _get_available_balance(
        self, strategy: Strategy, order_config: dict
    ) -> Optional[Decimal]:
        """DB에서 호가 통화 잔고 조회"""
        try:
            result = await self.db.execute(
                select(Balance).where(
                    Balance.user_id == strategy.user_id,
                    Balance.exchange_id == self.settings.EXCHANGE_ID,
                    Balance.symbol == self.settings.QUOTE_CURRENCY,
                )
            )
            balance = result.scalar_one_or_none()
            if balance:
                return Decimal(str(balance.available))
        except Exception as exc:
            logger.error("잔고 조회 실패: %s", exc)
        return None

    async def _get_portfolio_position(self, strategy: Strategy) -> Optional[Portfolio]:
        result = await self.db.execute(
            select(Portfolio).where(
                Portfolio.user_id == strategy.user_id,
                Portfolio.exchange_id == self.settings.EXCHANGE_ID,
                Portfolio.symbol == strategy.symbol,
            )
        )
        return result.scalar_one_or_none()

    async def _handle_position_exit(
        self,
        strategy: Strategy,
        strategy_dict: dict,
        position: Optional[Portfolio],
        current_price: Decimal,
        ohlcv_df: Optional[pd.DataFrame],
    ) -> Optional[dict]:
        order_config = strategy_dict.get("order_config") or {}
        if order_config.get("side", "buy") != "buy":
            return None

        if not position or Decimal(str(position.quantity or 0)) <= 0:
            await self._clear_trailing_peak(str(strategy.id))
            return None

        lock_key = f"position_exit_lock:{strategy.id}"
        acquired = await self.redis.set(lock_key, "1", nx=True, ex=10)
        if not acquired:
            return {"result": "skipped", "reason": "청산 처리 중"}

        try:
            exit_reason = await self._evaluate_exit_reason(
                strategy_dict,
                position,
                current_price,
                ohlcv_df,
            )
            if not exit_reason:
                return None

            held_quantity = Decimal(str(position.quantity))
            order_result = await self._place_split_orders(
                strategy_id=str(strategy.id),
                symbol=strategy.symbol,
                side="sell",
                order_type=order_config.get("type", "market"),
                quantity=held_quantity,
                current_price=current_price,
                order_config=order_config,
            )

            if order_result.get("success"):
                await self._clear_trailing_peak(str(strategy.id))

            return {
                "result": "position_exit" if order_result.get("success") else "position_exit_failed",
                "reason": exit_reason,
                "order": order_result,
            }
        finally:
            await self.redis.delete(lock_key)

    async def _evaluate_exit_reason(
        self,
        strategy: dict,
        position: Portfolio,
        current_price: Decimal,
        ohlcv_df: Optional[pd.DataFrame],
    ) -> Optional[str]:
        exit_condition = strategy.get("exit_condition")
        if exit_condition and ohlcv_df is not None:
            try:
                exit_result = self.evaluator.evaluate(exit_condition, ohlcv_df)
                if exit_result.matched:
                    return "custom_exit_condition"
            except Exception as exc:
                logger.warning("청산 조건 평가 실패: strategy=%s error=%s", strategy["id"], exc)

        order_config = strategy.get("order_config") or {}
        entry_price = Decimal(str(position.avg_buy_price or 0))
        if entry_price <= 0:
            return None

        stop_loss_pct = order_config.get("stop_loss_pct")
        if stop_loss_pct:
            stop_loss_price = entry_price * (Decimal("1") - Decimal(str(stop_loss_pct)) / Decimal("100"))
            if current_price <= stop_loss_price:
                return "stop_loss"

        take_profit_pct = order_config.get("take_profit_pct")
        if take_profit_pct:
            take_profit_price = entry_price * (Decimal("1") + Decimal(str(take_profit_pct)) / Decimal("100"))
            if current_price >= take_profit_price:
                return "take_profit"

        trailing_stop_pct = order_config.get("trailing_stop_pct")
        if order_config.get("trailing_stop") and trailing_stop_pct:
            peak_price = await self._update_trailing_peak(strategy["id"], current_price, entry_price)
            trailing_price = peak_price * (Decimal("1") - Decimal(str(trailing_stop_pct)) / Decimal("100"))
            if current_price <= trailing_price:
                return "trailing_stop"

        return None

    async def _place_split_orders(
        self,
        strategy_id: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        current_price: Decimal,
        order_config: dict,
    ) -> dict:
        split_count = max(1, int(order_config.get("split_count", 1) or 1))
        tranche_quantities = self.risk_manager.build_split_quantities(
            quantity,
            split_count,
            current_price,
        )

        orders: list[dict] = []
        for tranche_quantity in tranche_quantities:
            order_price = None
            quote_amount = None
            if (
                self.settings.EXCHANGE_ID == "upbit"
                and order_type == "market"
                and side == "buy"
            ):
                order_price = current_price
                quote_amount = tranche_quantity * current_price

            result = await self.order_manager.place_order(
                strategy_id=strategy_id,
                exchange_id=self.settings.EXCHANGE_ID,
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=tranche_quantity,
                price=order_price,
                quote_amount=quote_amount,
                order_config=order_config,
            )
            orders.append(result)

            if not result.get("success"):
                break

        success = bool(orders) and all(order.get("success") for order in orders)
        return {
            "success": success,
            "split_count": len(orders),
            "primary_order_id": orders[0].get("order_id") if orders else None,
            "orders": orders,
        }

    async def _set_trailing_peak(self, strategy_id: str, price: Decimal) -> None:
        await self.redis.set(f"trailing:peak:{strategy_id}", str(price))

    async def _clear_trailing_peak(self, strategy_id: str) -> None:
        await self.redis.delete(f"trailing:peak:{strategy_id}")

    async def _update_trailing_peak(
        self,
        strategy_id: str,
        current_price: Decimal,
        fallback_price: Decimal,
    ) -> Decimal:
        key = f"trailing:peak:{strategy_id}"
        raw = await self.redis.get(key)
        if raw:
            raw_value = raw.decode() if isinstance(raw, bytes) else raw
            peak_price = Decimal(str(raw_value))
        else:
            peak_price = fallback_price

        if current_price > peak_price or not raw:
            peak_price = current_price
            await self.redis.set(key, str(peak_price))

        return peak_price

    async def _check_conflicts(self, strategy: dict) -> list[str]:
        """
        동일 심볼에서 반대 방향 신호가 동시에 활성화된 전략 감지
        Returns: 충돌 전략 ID 목록 (없으면 빈 리스트)
        """
        # 같은 심볼의 다른 활성 전략 조회
        result = await self.db.execute(
            select(Strategy).where(
                Strategy.user_id == uuid.UUID(strategy["user_id"]),
                Strategy.symbol == strategy["symbol"],
                Strategy.is_active.is_(True),
                Strategy.id != strategy["id"],
            )
        )
        others = result.scalars().all()
        if not others:
            return []

        my_side = strategy["order_config"].get("side", "buy")
        conflicts = []
        for other in others:
            other_side = (other.order_config or {}).get("side", "buy") if other.order_config else "buy"
            if other_side != my_side:
                conflicts.append(str(other.id))

        # 우선순위가 높은 전략이 승리
        if conflicts:
            winner_priority = strategy.get("priority", 5)
            for other in others:
                if str(other.id) in conflicts and other.priority > winner_priority:
                    # 상대방이 우선순위가 더 높으면 내가 충돌 패배
                    return [str(other.id)]

        return []

    async def _record_conflict(self, strategy: dict, conflict_ids: list[str]) -> None:
        """전략 충돌 이력 DB 저장"""
        try:
            conflict = StrategyConflict(
                symbol=strategy["symbol"],
                strategy_ids=[strategy["id"]] + conflict_ids,
                conflict_type="opposite_signals",
                resolution="priority_win",
                winner_strategy_id=None,
            )
            self.db.add(conflict)
            await self.db.commit()
        except Exception as exc:
            logger.error("충돌 기록 실패: %s", exc)

    async def _consult_ai(
        self,
        strategy: dict,
        current_price: Decimal,
        ohlcv_df: pd.DataFrame,
    ) -> Optional[str]:
        """
        AI 자문 결과 반환
        ai_mode == 'off' → None (자문 불필요)
        Returns: "execute" | "hold" | "avoid" | None
        """
        ai_mode = strategy.get("ai_mode", "off")
        if ai_mode == "off":
            return "execute"  # AI 없이 바로 실행

        # semi_auto 승인 상태 확인
        if ai_mode == "semi_auto":
            approval = await self.ai_consultant.get_approval_request(strategy["id"])
            if approval:
                status = approval.get("status", "pending")
                if status == "approved":
                    await self.ai_consultant.clear_approval_request(strategy["id"])
                    logger.info("반자동 승인 소비: strategy=%s", strategy["id"])
                    return "execute"
                if status == "rejected":
                    logger.info("반자동 거절 상태 유지: strategy=%s", strategy["id"])
                    return "avoid"
                return "pending_approval"

        # 캐시된 자문 조회
        advice = await self.ai_consultant.get_cached_advice(strategy["id"])
        if advice is None:
            market_ctx = self._build_market_context(strategy, current_price, ohlcv_df)
            advice = await self.ai_consultant.refresh_advice(strategy, market_ctx)
            if advice is None:
                # AI 오류 시 전략에 따라 기본 동작
                return "execute" if ai_mode == "observe" else "hold"

        decision = advice.get("decision", "execute")

        if ai_mode == "observe":
            # 참고만 하고 항상 실행
            logger.info("AI 자문 참고 (observe): decision=%s", decision)
            return "execute"

        elif ai_mode == "semi_auto":
            if decision == "execute":
                await self.ai_consultant.create_approval_request(strategy, advice)
                await self._save_ai_consultation(
                    strategy_id=strategy["id"],
                    order_id=None,
                    advice_payload=advice,
                    user_approved=None,
                )
                logger.info("반자동 승인 대기 등록: strategy=%s", strategy["id"])
                return "pending_approval"
            await self._save_ai_consultation(
                strategy_id=strategy["id"],
                order_id=None,
                advice_payload=advice,
            )
            return decision

        elif ai_mode == "auto":
            if decision in {"hold", "avoid"}:
                await self._save_ai_consultation(
                    strategy_id=strategy["id"],
                    order_id=None,
                    advice_payload=advice,
                )
            return decision

        return "execute"

    def _build_market_context(
        self,
        strategy: dict,
        current_price: Decimal,
        ohlcv_df: pd.DataFrame,
    ) -> dict:
        """Claude 프롬프트용 시장 컨텍스트 구성"""
        close = ohlcv_df["close"]
        change_24h = 0.0
        if len(close) >= 2:
            prev = float(close.iloc[-24]) if len(close) >= 24 else float(close.iloc[0])
            curr = float(close.iloc[-1])
            change_24h = round((curr - prev) / prev * 100, 2) if prev > 0 else 0

        # 간단한 지표 요약
        indicators = {}
        try:
            import ta
            rsi = ta.momentum.rsi(close, 14)
            indicators["RSI_14"] = round(float(rsi.iloc[-1]), 2)

            ma20 = close.rolling(20).mean()
            ma50 = close.rolling(50).mean()
            indicators["MA20"] = round(float(ma20.iloc[-1]), 2)
            indicators["MA50"] = round(float(ma50.iloc[-1]), 2)

            volume = ohlcv_df["volume"]
            indicators["VOLUME"] = round(float(volume.iloc[-1]), 2)
            indicators["VOLUME_MA20"] = round(float(volume.rolling(20).mean().iloc[-1]), 2)
        except Exception:
            pass

        return {
            "symbol": strategy["symbol"],
            "price": str(current_price),
            "quote_currency": getattr(self.settings, "QUOTE_CURRENCY", "KRW"),
            "change_24h": change_24h,
            "indicators": indicators,
            "recent_trades": [],
            "btc_dominance": "N/A",
            "market_trend": "N/A",
        }

    async def _enqueue_hold_retry(self, strategy_id: str) -> None:
        """AI hold 결정 시 재시도 큐에 등록 (Redis)"""
        key = f"hold_retry:{strategy_id}"
        raw = await self.redis.get(key)
        count = int(raw) + 1 if raw else 1
        await self.redis.setex(key, 3600, count)
        logger.info("Hold 재시도 큐 등록: strategy=%s count=%d", strategy_id, count)

    async def _save_ai_consultation(
        self,
        strategy_id: str,
        order_id: Optional[str],
        advice_payload: Optional[dict] = None,
        user_approved: Optional[bool] = None,
    ) -> None:
        """AI 자문 결과 DB 저장"""
        try:
            cached = advice_payload or await self.ai_consultant.get_cached_advice(strategy_id)
            if not cached:
                return

            consult = AiConsultation(
                strategy_id=uuid.UUID(strategy_id),
                order_id=uuid.UUID(order_id) if order_id else None,
                model="claude-opus-4-6",
                prompt_version=str(cached.get("prompt_version", 1)),
                decision=cached.get("decision", "execute"),
                confidence=cached.get("confidence"),
                reason=cached.get("reason"),
                risk_level=cached.get("risk_level"),
                key_concerns=cached.get("key_concerns"),
                user_approved=user_approved,
                latency_ms=cached.get("latency_ms"),
            )
            self.db.add(consult)
            await self.db.commit()
        except Exception as exc:
            logger.error("AI 자문 DB 저장 실패: %s", exc)
