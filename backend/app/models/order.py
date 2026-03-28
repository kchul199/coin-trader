import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base


class Order(Base):
    """Trading order model."""

    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    strategy_id = Column(UUID(as_uuid=True), ForeignKey("strategies.id"), nullable=False)
    exchange_id = Column(String(50), nullable=False)
    exchange_order_id = Column(String(100), nullable=False)
    symbol = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False)  # 'buy' or 'sell'
    order_type = Column(String(20), nullable=False)  # 'limit', 'market', etc.
    price = Column(Numeric(20, 8), nullable=False)
    quantity = Column(Numeric(20, 8), nullable=False)
    filled_quantity = Column(Numeric(20, 8), nullable=False, default=0)
    avg_fill_price = Column(Numeric(20, 8), nullable=True)
    fee = Column(Numeric(20, 8), nullable=True)
    slippage_pct = Column(Numeric(5, 2), nullable=True)
    status = Column(String(50), default="pending", nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    filled_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Order(id={self.id}, symbol={self.symbol}, side={self.side})>"
