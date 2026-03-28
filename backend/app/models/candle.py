from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Column, String, Numeric, DateTime, PrimaryKeyConstraint

from app.models.base import Base


class Candle(Base):
    """OHLCV candle data model with composite primary key."""

    __tablename__ = "candles"

    symbol = Column(String(20), nullable=False, primary_key=True)
    exchange = Column(String(50), nullable=False, primary_key=True)
    timeframe = Column(String(10), nullable=False, primary_key=True)
    ts = Column(DateTime(timezone=True), nullable=False, primary_key=True)
    open = Column(Numeric(20, 8), nullable=False)
    high = Column(Numeric(20, 8), nullable=False)
    low = Column(Numeric(20, 8), nullable=False)
    close = Column(Numeric(20, 8), nullable=False)
    volume = Column(Numeric(20, 8), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("symbol", "exchange", "timeframe", "ts"),
    )

    def __repr__(self) -> str:
        return f"<Candle(symbol={self.symbol}, ts={self.ts})>"
