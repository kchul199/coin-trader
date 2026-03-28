import uuid
from datetime import datetime, timezone, date
from decimal import Decimal
from sqlalchemy import Column, Integer, Date, Numeric, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.models.base import Base


class BacktestResult(Base):
    """Backtest result model."""

    __tablename__ = "backtest_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    strategy_id = Column(UUID(as_uuid=True), ForeignKey("strategies.id"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    params_snapshot = Column(JSONB, nullable=False)
    initial_capital = Column(Numeric(20, 2), nullable=False)
    final_capital = Column(Numeric(20, 2), nullable=False)
    total_return_pct = Column(Numeric(10, 2), nullable=False)
    max_drawdown_pct = Column(Numeric(10, 2), nullable=False)
    sharpe_ratio = Column(Numeric(10, 4), nullable=False)
    win_rate = Column(Numeric(5, 2), nullable=False)
    profit_factor = Column(Numeric(10, 2), nullable=False)
    total_trades = Column(Integer, nullable=False)
    ai_on_return_pct = Column(Numeric(10, 2), nullable=True)
    ai_off_return_pct = Column(Numeric(10, 2), nullable=True)
    commission_pct = Column(Numeric(5, 2), nullable=False)
    slippage_pct = Column(Numeric(5, 2), nullable=False)
    equity_curve = Column(JSONB, nullable=False)
    trade_history = Column(JSONB, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<BacktestResult(strategy_id={self.strategy_id}, total_return_pct={self.total_return_pct})>"
