from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List
from datetime import date, datetime


class ServiceRequest(BaseModel):
    id: str
    quantity: int = 1


class BookingCalculateRequest(BaseModel):
    hotel_id: str
    room_id: int
    check_in: date
    check_out: date
    adults: int = 1
    children: int = 0
    services: List[ServiceRequest] = []


class ServiceBreakdown(BaseModel):
    id: str
    name: str
    price: float
    quantity: int
    charge_type: str
    amount: float


class BookingCalculateResponse(BaseModel):
    nights: int
    room_price_per_night: float
    room_total: float
    services_breakdown: List[ServiceBreakdown]
    services_total: float
    total_amount: float


class BookingCreateRequest(BaseModel):
    hotel_id: str
    room_id: int
    check_in: date
    check_out: date
    adults: int = 1
    children: int = 0
    services: List[ServiceRequest] = []

    # Данные гостя — передаются в Битрикс, не хранятся в нашей БД
    guest_full_name: str
    guest_birth_date: date
    guest_phone: str
    guest_email: EmailStr
    comment: Optional[str] = None

    passport_series: str
    passport_number: str
    passport_issued_by: str
    passport_issued_date: date

    captcha_token: str

    @field_validator("passport_series")
    @classmethod
    def check_series(cls, v):
        if not v.isdigit() or len(v) != 4:
            raise ValueError("Серия паспорта: ровно 4 цифры")
        return v

    @field_validator("passport_number")
    @classmethod
    def check_number(cls, v):
        if not v.isdigit() or len(v) != 6:
            raise ValueError("Номер паспорта: ровно 6 цифр")
        return v


class BookingCreateResponse(BaseModel):
    booking_id: str
    status: str
    expires_in: int           # секунды до истечения
    payment_url: str          # ссылка на сделку в Битрикс (= ссылка на оплату)
    bitrix_deal_id: Optional[int] = None
    bitrix_contact_id: Optional[int] = None


class BookingStatusResponse(BaseModel):
    booking_id: str
    status: str
    expires_in: Optional[int] = None
    bitrix_deal_url: Optional[str] = None


class BookingOut(BaseModel):
    id: str
    hotel_id: str
    room_id: int
    check_in: date
    check_out: date
    adults: int
    children: int
    total_amount: float
    status: str
    created_at: datetime
    bitrix_contact_id: Optional[int] = None
    bitrix_deal_id: Optional[int] = None
    bitrix_deal_url: Optional[str] = None

    model_config = {"from_attributes": True}
