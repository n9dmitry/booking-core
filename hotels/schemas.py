from pydantic import BaseModel
from typing import Optional, List


class RoomRuleOut(BaseModel):
    id: int
    category: str
    name: str
    description: Optional[str] = None
    icon_url: Optional[str] = None

    model_config = {"from_attributes": True}


class RoomOut(BaseModel):
    id: int
    hotel_id: str
    number: str
    name: str
    description: Optional[str] = None
    capacity_adults: int
    capacity_children: int
    base_price: float
    area_sqm: Optional[float] = None
    floor: Optional[int] = None
    is_active: bool
    rules: List[RoomRuleOut] = []

    model_config = {"from_attributes": True}


class HotelOut(BaseModel):
    id: str
    name: str
    address: str
    description: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    check_in_time: str
    check_out_time: str
    rules_html: Optional[str] = None
    is_active: bool

    model_config = {"from_attributes": True}


class ServiceOut(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    price: float
    charge_type: str

    model_config = {"from_attributes": True}


class HotelCreate(BaseModel):
    id: str
    name: str
    address: str
    description: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    check_in_time: str = "14:00"
    check_out_time: str = "12:00"
    rules_html: Optional[str] = None


class RoomCreate(BaseModel):
    hotel_id: str
    number: str
    name: str
    description: Optional[str] = None
    capacity_adults: int = 2
    capacity_children: int = 0
    base_price: float
    area_sqm: Optional[float] = None
    floor: Optional[int] = None
