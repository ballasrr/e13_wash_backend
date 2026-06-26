from sqlalchemy import Integer, String, DateTime, Boolean, Float
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"  # название таблицы в БД

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # уникальный идентификатор
    phone: Mapped[str] = mapped_column(String, unique=True, nullable=False)  # номер телефона — уникальный
    name: Mapped[str] = mapped_column(String, nullable=True)  # имя пользователя — необязательное
    bonus_balance: Mapped[float] = mapped_column(Float, default=0.0)  # бонусный баланс
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # активен ли пользователь
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)  # дата регистрации