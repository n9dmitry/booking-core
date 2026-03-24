from pydantic import BaseModel
from datetime import date
from typing import List


class AvailabilityOut(BaseModel):
    room_id: int
    from_date: str
    to_date: str
    blocked_dates: List[str]
