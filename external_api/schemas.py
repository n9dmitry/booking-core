"""
Pydantic-схемы для внешнего API (сайт ↔ бэкенд).
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date


# ─── Запрос доступных номеров ─────────────────────────────────────────────────

class AvailabilityRequest(BaseModel):
    check_in: date
    check_out: date
    adults: int = Field(1, ge=1)
    children: int = Field(0, ge=0)


# ─── Номер ───────────────────────────────────────────────────────────────────

class RoomOut(BaseModel):
    id: int
    hotel_id: str
    number: str
    name: str
    description: Optional[str]
    capacity_adults: int
    capacity_children: int
    base_price: float
    price_for_stay: float
    nights: int
    area_sqm: Optional[float]
    floor: Optional[int]
    photos: Optional[list]
    is_available: bool


# ─── Отель ───────────────────────────────────────────────────────────────────

class HotelOut(BaseModel):
    id: str
    name: str
    address: str
    description: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    check_in_time: str
    check_out_time: str
    rules_html: Optional[str]


# ─── Запрос бронирования ─────────────────────────────────────────────────────

class OccupancyInfo(BaseModel):
    adults: int = Field(1, ge=0)
    children: int = Field(0, ge=0)
    adult_room_id: Optional[int] = None
    child_room_id: Optional[int] = None


class BookingRequest(BaseModel):
    """
    Запрос бронирования от сайта.

    guest_data_encrypted — зашифрованный Fernet-токен с данными гостя:
    {
        full_name, birth_date, phone, email,
        passport: { series, number, issued_by, issued_date, registration }
    }

    source — метка сайта/канала откуда пришла бронь.
    Автоматически проставляется сайтом из label токена.
    Отображается в сделке Битрикс24.
    """
    room_id: Optional[int] = None
    check_in: date
    check_out: date
    occupancy: OccupancyInfo
    guest_data_encrypted: str = Field(..., description="Зашифрованные данные гостя (Fernet)")
    source: Optional[str] = Field(None, description="Метка источника (название сайта/канала)")
    comment: Optional[str] = None


# ─── Ответ бронирования ───────────────────────────────────────────────────────

class BookingOut(BaseModel):
    booking_id: str
    status: str
    hotel_id: str
    room_id: int
    check_in: date
    check_out: date
    adults: int
    children: int
    total_amount: float
    expires_at: Optional[str]
    source: Optional[str]
    message: str


class BookingSplitOut(BaseModel):
    adult_booking: BookingOut
    child_booking: BookingOut
    total_amount: float
    message: str


# ─── Статус брони ─────────────────────────────────────────────────────────────

class BookingStatusOut(BaseModel):
    booking_id: str
    status: str
    is_active: bool
    expires_at: Optional[str]
    room_id: int
    hotel_id: str
    check_in: date
    check_out: date
    source: Optional[str]
