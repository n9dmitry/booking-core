from sqlalchemy import String, Integer, Float, Boolean, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, List
from database import Base


class Hotel(Base):
    __tablename__ = "hotels"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str] = mapped_column(String(500))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    check_in_time: Mapped[str] = mapped_column(String(10), default="14:00")
    check_out_time: Mapped[str] = mapped_column(String(10), default="12:00")
    rules_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    rooms: Mapped[List["Room"]] = relationship("Room", back_populates="hotel", lazy="selectin")


class RoomRule(Base):
    __tablename__ = "room_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    icon_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class RoomRuleLink(Base):
    __tablename__ = "room_rule_links"

    room_id: Mapped[int] = mapped_column(Integer, ForeignKey("rooms.id"), primary_key=True)
    rule_id: Mapped[int] = mapped_column(Integer, ForeignKey("room_rules.id"), primary_key=True)


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hotel_id: Mapped[str] = mapped_column(String(50), ForeignKey("hotels.id"))
    number: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    capacity_adults: Mapped[int] = mapped_column(Integer, default=2)
    capacity_children: Mapped[int] = mapped_column(Integer, default=0)
    base_price: Mapped[float] = mapped_column(Float)
    area_sqm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    floor: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    photos: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    hotel: Mapped["Hotel"] = relationship("Hotel", back_populates="rooms")


class AdditionalService(Base):
    __tablename__ = "additional_services"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price: Mapped[float] = mapped_column(Float)
    charge_type: Mapped[str] = mapped_column(String(20), default="once")  # once | per_night
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class HotelService(Base):
    __tablename__ = "hotel_services"

    hotel_id: Mapped[str] = mapped_column(String(50), ForeignKey("hotels.id"), primary_key=True)
    service_id: Mapped[str] = mapped_column(String(50), ForeignKey("additional_services.id"), primary_key=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
