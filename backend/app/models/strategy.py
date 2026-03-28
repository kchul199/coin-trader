import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, SmallInteger, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.models.base import Base


class Strategy(Base):
    """Trading strategy model."""

    __tablename__ = "strategies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)
    symbol = Column(String(20), nullable=False)
    timeframe = Column(String(10), nullable=False)
    condition_tree = Column(JSONB, nullable=False)
    order_config = Column(JSONB, nullable=False)
    exit_condition = Column(JSONB, nullable=True)
    ai_mode = Column(String(50), default="off", nullable=False)
    priority = Column(SmallInteger, default=5, nullable=False)
    hold_retry_interval = Column(Integer, default=300, nullable=False)
    hold_max_retry = Column(SmallInteger, default=3, nullable=False)
    is_active = Column(Boolean, default=False, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Strategy(id={self.id}, user_id={self.user_id}, symbol={self.symbol})>"
