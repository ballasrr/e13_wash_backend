from __future__ import annotations
from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from datetime import datetime

if TYPE_CHECKING:
    from app.models.user import User

class PaymentMethod(Base):
    __tablename__ = "payment_methods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    yookassa_payment_method_id: Mapped[str] = mapped_column(String, nullable=False)  # токен способа оплаты в ЮКасса
    card_last4: Mapped[str] = mapped_column(String, nullable=True)
    card_brand: Mapped[str] = mapped_column(String, nullable=True)  # Visa/Mastercard/МИР
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship("User", back_populates="payment_methods")