from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin


class CreditPurchase(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "credit_purchases"
    __table_args__ = (UniqueConstraint("provider_order_id", name="uq_credit_purchase_provider_order"),)

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    pack_code: Mapped[str] = mapped_column(String(64), nullable=False)
    credits: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", server_default="pending")
    provider_order_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    provider_payment_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, unique=True)
