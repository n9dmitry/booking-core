from sqlalchemy import Integer, Boolean, Date, String, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from datetime import date
from typing import Optional
from database import Base


class RoomAvailability(Base):
    """One row per (room_id, date) — present means blocked."""
    __tablename__ = "rooms_availability"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_id: Mapped[int] = mapped_column(Integer, ForeignKey("rooms.id"))
    date: Mapped[date] = mapped_column(Date)
    booking_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        UniqueConstraint("room_id", "date", name="uq_room_date"),
        Index("ix_avail_room_date", "room_id", "date"),
    )
