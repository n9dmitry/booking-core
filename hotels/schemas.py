# hotels/schemas.py
from pydantic import BaseModel

class HotelOut(BaseModel):
    id: str
    name: str
    domain: str | None = None
    address: str | None = None
    description: str | None = None

    model_config = {"from_attributes": True}   # ← современный способ (pydantic v2)

class RoomOut(BaseModel):
    id: str
    hotel_id: str
    name: str
    code: str | None = None
    capacity_adults: int
    capacity_children: int
    price_base: float
    description: str | None = None

    model_config = {"from_attributes": True}