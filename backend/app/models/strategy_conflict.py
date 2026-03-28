import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.models.base import Base


class StrategyConflict(Base):
    """Strategy conflict resolution model."""

    __tablename__ = "strategy_conflicts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol = Column(String(20), nullable=False)
    strategy_ids = Column(JSONB, nullable=False)  # List of strategy IDs in conflict
    conflict_type = Column(String(100), nullable=False)
    resolution = Column(String(100), nullable=False)
    winner_strategy_id = Column(UUID(as_uuid=True), nullable=True)
    occurred_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<StrategyConflict(symbol={self.symbol}, conflict_type={self.conflict_type})>"
