from __future__ import annotations
from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from datetime import datetime

if TYPE_CHECKING:
    from app.models.transaction import Transaction

class Machine(Base):
    __tablename__ = "machines"  # название таблицы в БД

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)  # CrestWave machine ID (например 35863), задаётся вручную
    serial: Mapped[str] = mapped_column(String, unique=True, nullable=False)  # серийный номер терминала
    name: Mapped[str] = mapped_column(String, nullable=False)  # название мойки
    address: Mapped[str] = mapped_column(String, nullable=True)  # адрес мойки
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # активна ли мойка
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)  # дата создания
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  # дата обновления

    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="machine")  # связь с транзакциями