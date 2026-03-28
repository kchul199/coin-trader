import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.models.base import Base


class AIConsultation(Base):
    """AI consultation record model."""

    __tablename__ = "ai_consultations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    strategy_id = Column(UUID(as_uuid=True), ForeignKey("strategies.id"), nullable=False)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=True)
    model = Column(String(100), nullable=False)
    prompt_version = Column(String(50), nullable=False)
    decision = Column(String(100), nullable=False)
    confidence = Column(Integer, nullable=False)  # 0-100
    reason = Column(String(1000), nullable=True)
    risk_level = Column(String(50), nullable=True)
    key_concerns = Column(JSONB, nullable=True)
    user_approved = Column(Boolean, nullable=True)
    latency_ms = Column(Integer, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<AIConsultation(id={self.id}, decision={self.decision})>"
