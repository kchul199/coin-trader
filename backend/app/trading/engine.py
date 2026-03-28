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
from app.trading.strategy_evaluator import StrategyEvaluator, ConditionResult
from app.trading.risk_manager import RiskManager
from app.trading.order_manager import OrderManager
from app.trading.ai_consultant import AIConsultant
from app.exchange.ccxt_adapter import CcxtAdapter
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
        self.order_manager = OrderManager(exchange, ws_manager, db)
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
            "name": strategy.name,
            "symbol": strategy.symbol,
            "timeframe": strategy.timeframe,
            "ai_mode": strategy.ai_mode,
            "priority": strategy.priority,
            "condition_tree": strategy.condition_tree,
            "order_config": strategy.order_config,
            "hold_retry_interval": strategy.hold_retry_interval,
            "hold_max_retry": strategy.hold_max_retry,
        }

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

        if ai_decision == "hold":
            await self._enqueue_hold_retry(strategy_id)
            return {"result": "ai_hold", "ai_decision": ai_decision}

        # 8) 잔고 확인 및 수량 계산
        balance = await self._get_available_balance(strategy, strategy_dict["order_config"])
        if balance is None or not self.risk_manager.validate_min_balance(balance):
            return {"result": "skipped", "reason": f"잔고 부족: {balance} USDT"}

        quantity = self.risk_manager.calculate_order_quantity(
            strategy_dict["order_config"],
            balance,
            current_price,
        )
        if quantity <= 0:
            return {"result": "skipped", "reason": "주문 수량 계산 오류"}

        # 9) 주문 실행
        order_config = strategy_dict["order_config"]
        order_result = await self.order_manager.place_order(
            strategy_id=strategy_id,
            exchange_id=self.settings.EXCHANGE_ID,
            symbol=strategy.symbol,
            side=order_config.get("side", "buy"),
            order_type=order_config.get("type", "market"),
            quantity=quantity,
        )

        # 10) AI 자문 결과 DB 저장
        if ai_decision is not None:
            await self._save_ai_consultation(
                strategy_id=strategy_id,
                order_id=order_result.get("order_id") if order_result["success"] else None,
            )

        return {
            "result": "order_placed" if order_result["success"] else "order_failed",
            "order": order_result,
            "triggered_conditions": condition_result.triggered,
        }

    # ------------------------------------------------------------------ #
    # 보조 메서드
    # ------------------------------------------------------------------ #

    async def _load_strategy(self, strategy_id: str) -> Optional[Strategy]:
        result = await self.db.execute(
            select(Strategy).where(Strategy.id == strategy_id)
        )
        return result.scalar_one_or_none()

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
        cache_key = f"price:{self.settings.EXCHANGE_ID}:{symbol}"
        raw = await self.redis.get(cache_key)
        if raw:
            try:
                data = json.loads(raw)
                return Decimal(str(data.get("price") or data.get("last") or 0))
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
        """DB에서 USDT 잔고 조회"""
        try:
            result = await self.db.execute(
                select(Balance).where(
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

    async def _check_conflicts(self, strategy: dict) -> list[str]:
        """
        동일 심볼에서 반대 방향 신호가 동시에 활성화된 전략 감지
        Returns: 충돌 전략 ID 목록 (없으면 빈 리스트)
        """
        # 같은 심볼의 다른 활성 전략 조회
        result = await self.db.execute(
            select(Strategy).where(
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

        # 캐시된 자문 조회
        cached = await self.ai_consultant.get_cached_advice(strategy["id"])
        if cached:
            decision = cached.get("decision", "execute")
        else:
            # 시장 컨텍스트 구성
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
            # TODO: Phase 4에서 승인 대기 큐 구현
            # 지금은 execute만 통과, 나머지는 hold
            if decision == "execute":
                return "execute"
            return "hold"

        elif ai_mode == "auto":
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
            "quote_currency": getattr(self.settings, "QUOTE_CURRENCY", "USDT"),
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
    ) -> None:
        """AI 자문 결과 DB 저장"""
        try:
            cached = await self.ai_consultant.get_cached_advice(strategy_id)
            if not cached:
                return

            consult = AiConsultation(
                strategy_id=strategy_id,
                order_id=order_id,
                model="claude-opus-4-6",
                prompt_version=str(cached.get("prompt_version", 1)),
                decision=cached.get("decision", "execute"),
                confidence=cached.get("confidence"),
                reason=cached.get("reason"),
                risk_level=cached.get("risk_level"),
                key_concerns=cached.get("key_concerns"),
                latency_ms=cached.get("latency_ms"),
            )
            self.db.add(consult)
            await self.db.commit()
        except Exception as exc:
            logger.error("AI 자문 DB 저장 실패: %s", exc)
