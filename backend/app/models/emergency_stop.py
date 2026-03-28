import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.models.base import Base


class EmergencyStop(Base):
    """Emergency stop record model."""

    __tablename__ = "emergency_stops"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    strategy_id = Column(UUID(as_uuid=True), ForeignKey("strategies.id"), nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    reason = Column(String(500), nullable=False)
    cancelled_orders = Column(JSONB, nullable=False)  # List of cancelled order IDs
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<EmergencyStop(id={self.id}, user_id={self.user_id})>"
