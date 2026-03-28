import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base


class Portfolio(Base):
    """User portfolio model tracking positions."""

    __tablename__ = "portfolios"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    symbol = Column(String(20), nullable=False)
    exchange_id = Column(String(50), nullable=False)
    quantity = Column(Numeric(20, 8), nullable=False)
    avg_buy_price = Column(Numeric(20, 8), nullable=False)
    initial_capital = Column(Numeric(20, 8), nullable=False)
    last_updated = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("user_id", "symbol", "exchange_id", name="uq_portfolio_user_symbol_exchange"),
    )

    def __repr__(self) -> str:
        return f"<Portfolio(user_id={self.user_id}, symbol={self.symbol})>"
