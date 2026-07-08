from __future__ import annotations
from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, DateTime, Float, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from datetime import datetime

if TYPE_CHECKING:
    from app.models.machine import Machine
    from app.models.user import User

class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    machine_id: Mapped[int] = mapped_column(Integer, ForeignKey("machines.id"), nullable=False)
    program_name: Mapped[str] = mapped_column(String, nullable=False)

    total_amount: Mapped[float] = mapped_column(Float, nullable=False)
    bonus_used: Mapped[float] = mapped_column(Float, default=0.0)
    paid_amount: Mapped[float] = mapped_column(Float, nullable=False)

    payment_method_id: Mapped[int] = mapped_column(Integer, ForeignKey("payment_methods.id"), nullable=True)
    yookassa_payment_id: Mapped[str] = mapped_column(String, nullable=True)
    payment_method_type: Mapped[str] = mapped_column(String, nullable=True)

    status: Mapped[str] = mapped_column(String, default="pending")
    crestwave_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    crestwave_event_id: Mapped[str] = mapped_column(String, nullable=True)
    bonus_debited: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    paid_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    machine: Mapped["Machine"] = relationship("Machine", back_populates="transactions")
    user: Mapped["User"] = relationship("User", back_populates="transactions")