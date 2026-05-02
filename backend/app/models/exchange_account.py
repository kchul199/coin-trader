import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, LargeBinary, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base


class ExchangeAccount(Base):
    """Exchange account credentials model."""

    __tablename__ = "exchange_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    exchange_id = Column(String(50), nullable=False)
    api_key_encrypted = Column(LargeBinary, nullable=False)
    api_secret_encrypted = Column(LargeBinary, nullable=False)
    is_testnet = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<ExchangeAccount(id={self.id}, user_id={self.user_id}, exchange_id={self.exchange_id})>"
