import uuid
from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, Integer, Float, DateTime, Date, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base
import enum


class BookingStatus(str, enum.Enum):
    WAITING_PAYMENT = "waiting_payment"
    PAID = "paid"
    CANCELLED = "cancelled"
    CANCELLED_TIMEOUT = "cancelled_timeout"
    CHECKED_IN = "checked_in"
    CHECKED_OUT = "checked_out"


class StatusMapping(Base):
    """Maps Bitrix24 STAGE_ID → internal BookingStatus."""
    __tablename__ = "status_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    internal_status: Mapped[str] = mapped_column(String(50), unique=True)
    bitrix_stage_id: Mapped[str] = mapped_column(String(50))
    description: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True,
                                    default=lambda: str(uuid.uuid4()))
    hotel_id: Mapped[str] = mapped_column(String(50))
    room_id: Mapped[int] = mapped_column(Integer, ForeignKey("rooms.id"))

    # ── Даты и гости ──────────────────────────────────────────────────────────
    check_in: Mapped[date] = mapped_column(Date)
    check_out: Mapped[date] = mapped_column(Date)
    adults: Mapped[int] = mapped_column(Integer, default=1)
    children: Mapped[int] = mapped_column(Integer, default=0)

    # ── Ценообразование ───────────────────────────────────────────────────────
    room_total: Mapped[float] = mapped_column(Float)
    services_total: Mapped[float] = mapped_column(Float, default=0)
    total_amount: Mapped[float] = mapped_column(Float)
    services_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Статус ────────────────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(String(30), default=BookingStatus.WAITING_PAYMENT)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # ── Битрикс24 — единственное место хранения данных клиента ───────────────
    bitrix_contact_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bitrix_deal_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bitrix_deal_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow,
                                                 onupdate=datetime.utcnow)

    # cascade="all, delete-orphan" — при удалении Booking удаляет всю историю
    history: Mapped[list["BookingStatusHistory"]] = relationship(
        "BookingStatusHistory", back_populates="booking", lazy="selectin",
        cascade="all, delete-orphan",
    )


class BookingStatusHistory(Base):
    __tablename__ = "booking_status_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # ondelete="CASCADE" — на уровне БД (SQLite с PRAGMA foreign_keys=ON)
    booking_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False
    )
    old_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    new_status: Mapped[str] = mapped_column(String(50))
    comment: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    booking: Mapped["Booking"] = relationship("Booking", back_populates="history")
