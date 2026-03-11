# hotels/models.py
from sqlalchemy import String, Integer, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base               # ← из корня


class Hotel(Base):
    __tablename__ = "hotels"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    domain: Mapped[str] = mapped_column(String(100), nullable=True)
    address: Mapped[str] = mapped_column(String(250), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    checkin_time: Mapped[str] = mapped_column(String(10), default="14:00")
    checkout_time: Mapped[str] = mapped_column(String(10), default="12:00")
    rules_html: Mapped[str] = mapped_column(Text, nullable=True)

    rooms: Mapped[list["Room"]] = relationship("Room", back_populates="hotel")


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    hotel_id: Mapped[str] = mapped_column(String(50), ForeignKey("hotels.id"), index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=True)
    capacity_adults: Mapped[int] = mapped_column(Integer, default=2)
    capacity_children: Mapped[int] = mapped_column(Integer, default=1)
    price_base: Mapped[float] = mapped_column(Integer)          # лучше сделать Float
    description: Mapped[str] = mapped_column(Text, nullable=True)

    hotel: Mapped["Hotel"] = relationship("Hotel", back_populates="rooms")