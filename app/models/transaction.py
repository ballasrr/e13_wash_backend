from __future__ import annotations
from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, DateTime, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from datetime import datetime

if TYPE_CHECKING:
    from app.models.machine import Machine

class Transaction(Base):
    __tablename__ = "transactions"  # название таблицы в БД

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # уникальный идентификатор
    machine_id: Mapped[int] = mapped_column(Integer, ForeignKey("machines.id"), nullable=False)  # ссылка на мойку
    serial: Mapped[str] = mapped_column(String, nullable=False)  # серийный номер терминала
    amount: Mapped[float] = mapped_column(Float, nullable=False)  # сумма транзакции
    payment_type: Mapped[str] = mapped_column(String, nullable=False)  # тип оплаты
    program_name: Mapped[str] = mapped_column(String, nullable=True)  # название программы мойки
    payer_id: Mapped[str] = mapped_column(String, nullable=True)  # идентификатор плательщика
    status: Mapped[str] = mapped_column(String, default="success")  # статус транзакции
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)  # дата создания

    machine: Mapped[Machine] = relationship("Machine", back_populates="transactions")  # связь с мойкой