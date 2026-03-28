"""
BacktestService — 이벤트 드리븐 백테스트 엔진

흐름:
1. DB에서 전략 로드 → OHLCV 기간 데이터 조회
2. 각 캔들 순회: StrategyEvaluator로 조건 평가
3. 신호 발생 시 커미션/슬리피지 적용 후 가상 체결
4. 자산 곡선 추적 → 성과 지표 계산
5. BacktestResult DB 저장
"""
from __future__ import annotations

import asyncio
import logging
import math
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_DOWN
from typing import Any

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.backtest_result import BacktestResult
from app.models.candle import Candle
from app.models.strategy import Strategy
from app.trading.strategy_evaluator import StrategyEvaluator

logger = logging.getLogger(__name__)

RISK_FREE_RATE = 0.0  # 연 무위험이자율 (연율화 Sharpe용)


@dataclass
class SimTrade:
    """시뮬레이션 거래 기록"""
    entry_time: str
    exit_time: str
    entry_price: float
    exit_price: float
    quantity: float
    side: str  # "buy"
    pnl: float
    pnl_pct: float
    commission: float


@dataclass
class BacktestState:
    """백테스트 런타임 상태"""
    capital: float
    peak_capital: float
    position_qty: float = 0.0
    position_price: float = 0.0
    position_entry_time: str = ""
    trades: list[SimTrade] = field(default_factory=list)
    equity_curve: list[dict] = field(default_factory=list)
    max_drawdown: float = 0.0


class BacktestService:
    """이벤트 드리븐 백테스트 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.evaluator = StrategyEvaluator()

    async def run(
        self,
        strategy_id: str,
        user_id: str,
        start_date: date,
        end_date: date,
        initial_capital: float,
        commission_pct: float = 0.05,
        slippage_pct: float = 0.02,
    ) -> BacktestResult:
        """백테스트 실행 후 결과 저장"""
        # 1. 전략 로드
        strategy = await self._load_strategy(strategy_id, user_id)

        # 2. OHLCV 데이터 조회
        ohlcv_df = await self._load_candles(
            symbol=strategy.symbol,
            timeframe=strategy.timeframe,
            start_date=start_date,
            end_date=end_date,
        )

        if ohlcv_df.empty or len(ohlcv_df) < 30:
            raise ValueError("백테스트에 필요한 충분한 캔들 데이터가 없습니다 (최소 30개 필요)")

        # 3. 시뮬레이션 실행
        state = BacktestState(
            capital=initial_capital,
            peak_capital=initial_capital,
        )

        params_snapshot = {
            "symbol": strategy.symbol,
            "timeframe": strategy.timeframe,
            "order_config": strategy.order_config,
            "ai_mode": strategy.ai_mode,
        }

        await asyncio.get_event_loop().run_in_executor(
            None,
            self._simulate,
            state,
            ohlcv_df,
            strategy.condition_tree,
            strategy.exit_condition,
            strategy.order_config,
            commission_pct,
            slippage_pct,
            initial_capital,
        )

        # 4. 성과 지표 계산
        metrics = self._calculate_metrics(state, initial_capital, ohlcv_df)

        # 5. DB 저장
        result = BacktestResult(
            id=uuid.uuid4(),
            strategy_id=uuid.UUID(strategy_id),
            start_date=start_date,
            end_date=end_date,
            params_snapshot=params_snapshot,
            initial_capital=Decimal(str(initial_capital)),
            final_capital=Decimal(str(round(state.capital, 2))),
            total_return_pct=Decimal(str(round(metrics["total_return_pct"], 2))),
            max_drawdown_pct=Decimal(str(round(metrics["max_drawdown_pct"], 2))),
            sharpe_ratio=Decimal(str(round(metrics["sharpe_ratio"], 4))),
            win_rate=Decimal(str(round(metrics["win_rate"], 2))),
            profit_factor=Decimal(str(round(metrics["profit_factor"], 2))),
            total_trades=metrics["total_trades"],
            ai_on_return_pct=None,
            ai_off_return_pct=None,
            commission_pct=Decimal(str(commission_pct)),
            slippage_pct=Decimal(str(slippage_pct)),
            equity_curve=state.equity_curve,
            trade_history=[self._trade_to_dict(t) for t in state.trades],
        )

        self.db.add(result)
        await self.db.commit()
        await self.db.refresh(result)

        logger.info(
            "Backtest complete: strategy=%s return=%.2f%% trades=%d",
            strategy_id,
            metrics["total_return_pct"],
            metrics["total_trades"],
        )
        return result

    # ───────────────────────────────────────────── private helpers ─────

    async def _load_strategy(self, strategy_id: str, user_id: str) -> Strategy:
        result = await self.db.execute(
            select(Strategy).where(
                Strategy.id == uuid.UUID(strategy_id),
                Strategy.user_id == uuid.UUID(user_id),
            )
        )
        strategy = result.scalar_one_or_none()
        if not strategy:
            raise ValueError(f"전략을 찾을 수 없습니다: {strategy_id}")
        return strategy

    async def _load_candles(
        self,
        symbol: str,
        timeframe: str,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        start_dt = datetime(start_date.year, start_date.month, start_date.day, tzinfo=timezone.utc)
        end_dt = datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59, tzinfo=timezone.utc)

        result = await self.db.execute(
            select(Candle)
            .where(
                Candle.symbol == symbol,
                Candle.timeframe == timeframe,
                Candle.ts >= start_dt,
                Candle.ts <= end_dt,
            )
            .order_by(Candle.ts.asc())
        )
        candles = result.scalars().all()

        if not candles:
            return pd.DataFrame()

        rows = [
            {
                "time": c.ts,
                "open": float(c.open),
                "high": float(c.high),
                "low": float(c.low),
                "close": float(c.close),
                "volume": float(c.volume),
            }
            for c in candles
        ]
        df = pd.DataFrame(rows)
        df.set_index("time", inplace=True)
        return df

    def _simulate(
        self,
        state: BacktestState,
        ohlcv: pd.DataFrame,
        condition_tree: dict,
        exit_condition: dict | None,
        order_config: dict,
        commission_pct: float,
        slippage_pct: float,
        initial_capital: float,
    ) -> None:
        """캔들 순회 시뮬레이션 (동기 — executor에서 실행)"""
        lookback = 50  # 지표 계산에 필요한 최소 캔들 수

        for i in range(lookback, len(ohlcv)):
            window = ohlcv.iloc[: i + 1]
            current_bar = ohlcv.iloc[i]
            ts = ohlcv.index[i]
            close_price = float(current_bar["close"])
            ts_str = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)

            # ─── 포지션 보유 중: 청산 조건 확인 ───
            if state.position_qty > 0:
                should_exit = False

                # 커스텀 청산 조건
                if exit_condition:
                    try:
                        exit_result = self.evaluator.evaluate(exit_condition, window)
                        if exit_result.matched:
                            should_exit = True
                    except Exception:
                        pass

                # 고정 청산 조건: stop_loss / take_profit
                cfg = order_config or {}
                if not should_exit:
                    stop_loss_pct = cfg.get("stop_loss_pct")
                    take_profit_pct = cfg.get("take_profit_pct")
                    if stop_loss_pct and state.position_price > 0:
                        if close_price <= state.position_price * (1 - stop_loss_pct / 100):
                            should_exit = True
                    if take_profit_pct and state.position_price > 0 and not should_exit:
                        if close_price >= state.position_price * (1 + take_profit_pct / 100):
                            should_exit = True

                if should_exit:
                    self._close_position(
                        state, close_price, ts_str, commission_pct, slippage_pct
                    )

            # ─── 포지션 없음: 진입 조건 확인 ───
            if state.position_qty == 0:
                try:
                    entry_result = self.evaluator.evaluate(condition_tree, window)
                except Exception:
                    entry_result = None

                if entry_result and entry_result.matched:
                    self._open_position(
                        state, close_price, ts_str, order_config, commission_pct, slippage_pct
                    )

            # ─── 자산 곡선 기록 ───
            portfolio_value = state.capital
            if state.position_qty > 0:
                portfolio_value += state.position_qty * close_price

            state.equity_curve.append({"time": ts_str, "value": round(portfolio_value, 2)})

            # 최대 낙폭 추적
            if portfolio_value > state.peak_capital:
                state.peak_capital = portfolio_value
            drawdown = (state.peak_capital - portfolio_value) / state.peak_capital * 100
            if drawdown > state.max_drawdown:
                state.max_drawdown = drawdown

        # ─── 기간 종료: 미청산 포지션 강제 청산 ───
        if state.position_qty > 0 and len(ohlcv) > 0:
            last_close = float(ohlcv.iloc[-1]["close"])
            last_ts = ohlcv.index[-1]
            last_ts_str = last_ts.isoformat() if hasattr(last_ts, "isoformat") else str(last_ts)
            self._close_position(state, last_close, last_ts_str, commission_pct, slippage_pct)

    def _open_position(
        self,
        state: BacktestState,
        price: float,
        ts: str,
        order_config: dict,
        commission_pct: float,
        slippage_pct: float,
    ) -> None:
        """가상 매수 체결"""
        cfg = order_config or {}
        entry_type = cfg.get("type", "balance_pct")
        slipped_price = price * (1 + slippage_pct / 100)

        if entry_type == "balance_pct":
            pct = float(cfg.get("balance_pct", 10)) / 100
            trade_amount = state.capital * pct
        elif entry_type == "fixed_amount":
            trade_amount = min(float(cfg.get("amount", 100)), state.capital)
        else:
            trade_amount = state.capital * 0.1  # 기본 10%

        if trade_amount <= 0 or state.capital < trade_amount:
            return

        commission = trade_amount * (commission_pct / 100)
        qty = (trade_amount - commission) / slipped_price

        state.capital -= (trade_amount)
        state.position_qty = qty
        state.position_price = slipped_price
        state.position_entry_time = ts

    def _close_position(
        self,
        state: BacktestState,
        price: float,
        ts: str,
        commission_pct: float,
        slippage_pct: float,
    ) -> None:
        """가상 매도 체결"""
        if state.position_qty <= 0:
            return

        slipped_price = price * (1 - slippage_pct / 100)
        gross_proceeds = state.position_qty * slipped_price
        commission = gross_proceeds * (commission_pct / 100)
        net_proceeds = gross_proceeds - commission

        entry_cost = state.position_qty * state.position_price
        pnl = net_proceeds - entry_cost
        pnl_pct = (pnl / entry_cost) * 100 if entry_cost > 0 else 0.0

        trade = SimTrade(
            entry_time=state.position_entry_time,
            exit_time=ts,
            entry_price=state.position_price,
            exit_price=slipped_price,
            quantity=state.position_qty,
            side="buy",
            pnl=round(pnl, 4),
            pnl_pct=round(pnl_pct, 4),
            commission=round(commission, 4),
        )
        state.trades.append(trade)
        state.capital += net_proceeds
        state.position_qty = 0.0
        state.position_price = 0.0
        state.position_entry_time = ""

    def _calculate_metrics(
        self,
        state: BacktestState,
        initial_capital: float,
        ohlcv: pd.DataFrame,
    ) -> dict:
        """성과 지표 계산"""
        final_capital = state.capital
        total_return_pct = ((final_capital - initial_capital) / initial_capital) * 100

        trades = state.trades
        total_trades = len(trades)
        winning = [t for t in trades if t.pnl > 0]
        losing = [t for t in trades if t.pnl <= 0]

        win_rate = (len(winning) / total_trades * 100) if total_trades > 0 else 0.0

        gross_profit = sum(t.pnl for t in winning)
        gross_loss = abs(sum(t.pnl for t in losing))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)

        # Sharpe ratio (일별 수익률 기준)
        sharpe = 0.0
        if len(state.equity_curve) >= 2:
            values = [e["value"] for e in state.equity_curve]
            daily_returns = []
            for i in range(1, len(values)):
                if values[i - 1] > 0:
                    daily_returns.append((values[i] - values[i - 1]) / values[i - 1])

            if len(daily_returns) >= 2:
                mean_r = sum(daily_returns) / len(daily_returns)
                variance = sum((r - mean_r) ** 2 for r in daily_returns) / len(daily_returns)
                std_r = math.sqrt(variance) if variance > 0 else 0.0
                if std_r > 0:
                    # 기간 캔들 수에 따라 연율화 계수 추정
                    sharpe = (mean_r / std_r) * math.sqrt(252)

        return {
            "total_return_pct": total_return_pct,
            "max_drawdown_pct": state.max_drawdown,
            "sharpe_ratio": sharpe,
            "win_rate": win_rate,
            "profit_factor": min(profit_factor, 999.99),  # overflow 방지
            "total_trades": total_trades,
        }

    @staticmethod
    def _trade_to_dict(t: SimTrade) -> dict:
        return {
            "entry_time": t.entry_time,
            "exit_time": t.exit_time,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "quantity": t.quantity,
            "side": t.side,
            "pnl": t.pnl,
            "pnl_pct": t.pnl_pct,
            "commission": t.commission,
        }

    @staticmethod
    def serialize_result(result: BacktestResult) -> dict:
        """API 응답용 직렬화"""
        return {
            "id": str(result.id),
            "strategy_id": str(result.strategy_id),
            "start_date": result.start_date.isoformat(),
            "end_date": result.end_date.isoformat(),
            "params_snapshot": result.params_snapshot,
            "initial_capital": float(result.initial_capital),
            "final_capital": float(result.final_capital),
            "total_return_pct": float(result.total_return_pct),
            "max_drawdown_pct": float(result.max_drawdown_pct),
            "sharpe_ratio": float(result.sharpe_ratio),
            "win_rate": float(result.win_rate),
            "profit_factor": float(result.profit_factor),
            "total_trades": result.total_trades,
            "ai_on_return_pct": float(result.ai_on_return_pct) if result.ai_on_return_pct is not None else None,
            "ai_off_return_pct": float(result.ai_off_return_pct) if result.ai_off_return_pct is not None else None,
            "commission_pct": float(result.commission_pct),
            "slippage_pct": float(result.slippage_pct),
            "equity_curve": result.equity_curve,
            "trade_history": result.trade_history,
            "created_at": result.created_at.isoformat(),
        }
