from __future__ import annotations
from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, DateTime, Boolean, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from datetime import datetime

if TYPE_CHECKING:
    from app.models.transaction import Transaction
    from app.models.payment_method import PaymentMethod

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phone: Mapped[str] = mapped_column(String, unique=True, nullable=False)  # номер телефона — уникальный, он же msisdn для CrestWave бонусов
    name: Mapped[str] = mapped_column(String, nullable=True)
    bonus_balance: Mapped[float] = mapped_column(Float, default=0.0)  # синхронизируется с CrestWave bonus account
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="user")
    payment_methods: Mapped[list["PaymentMethod"]] = relationship("PaymentMethod", back_populates="user")