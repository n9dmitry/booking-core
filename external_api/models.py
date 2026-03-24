"""Токены внешнего API для сайтов отелей."""
import secrets
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class HotelApiToken(Base):
    __tablename__ = "hotel_api_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hotel_id: Mapped[str] = mapped_column(String(50), ForeignKey("hotels.id", ondelete="CASCADE"))
    # Храним полный токен — администратор может посмотреть его снова
    token: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    label: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    @staticmethod
    def generate_token() -> str:
        return secrets.token_urlsafe(48)
