import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base


class Balance(Base):
    """User balance model for exchange accounts."""

    __tablename__ = "balances"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    exchange_id = Column(String(50), nullable=False)
    symbol = Column(String(20), nullable=False)
    available = Column(Numeric(20, 8), nullable=False, default=0)
    locked = Column(Numeric(20, 8), nullable=False, default=0)
    synced_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("user_id", "exchange_id", "symbol", name="uq_balance_user_exchange_symbol"),
    )

    def __repr__(self) -> str:
        return f"<Balance(user_id={self.user_id}, symbol={self.symbol})>"
