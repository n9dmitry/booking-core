from datetime import date
from typing import List, Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from hotels.models import Hotel, Room, RoomRule, RoomRuleLink, AdditionalService, HotelService
from stock.models import RoomAvailability
from utils import dates_in_range


async def get_all_hotels(db: AsyncSession) -> List[Hotel]:
    result = await db.execute(select(Hotel).where(Hotel.is_active == True))
    return result.scalars().all()


async def get_hotel(db: AsyncSession, hotel_id: str) -> Optional[Hotel]:
    return await db.get(Hotel, hotel_id)


async def get_hotel_rooms(
    db: AsyncSession,
    hotel_id: str,
    check_in: Optional[date] = None,
    check_out: Optional[date] = None,
    adults: int = 1,
) -> List[dict]:
    result = await db.execute(
        select(Room).where(and_(Room.hotel_id == hotel_id, Room.is_active == True))
    )
    rooms = result.scalars().all()

    # Filter by availability if dates provided
    if check_in and check_out:
        needed_dates = dates_in_range(check_in, check_out)
        available = []
        for room in rooms:
            blocked = await db.execute(
                select(RoomAvailability).where(
                    and_(
                        RoomAvailability.room_id == room.id,
                        RoomAvailability.date.in_(needed_dates),
                        RoomAvailability.is_blocked == True,
                    )
                )
            )
            if not blocked.scalars().first():
                available.append(room)
        rooms = available

    # Attach rules
    out = []
    for room in rooms:
        rules = await get_room_rules(db, room.id)
        out.append({"room": room, "rules": rules})
    return out


async def get_room_rules(db: AsyncSession, room_id: int) -> List[RoomRule]:
    result = await db.execute(
        select(RoomRule)
        .join(RoomRuleLink, RoomRule.id == RoomRuleLink.rule_id)
        .where(RoomRuleLink.room_id == room_id)
        .where(RoomRule.is_active == True)
    )
    return result.scalars().all()


async def get_hotel_services(db: AsyncSession, hotel_id: str) -> List[AdditionalService]:
    result = await db.execute(
        select(AdditionalService)
        .join(HotelService, AdditionalService.id == HotelService.service_id)
        .where(HotelService.hotel_id == hotel_id)
        .where(HotelService.is_active == True)
        .where(AdditionalService.is_active == True)
    )
    return result.scalars().all()


async def create_hotel(db: AsyncSession, data: dict) -> Hotel:
    hotel = Hotel(**data)
    db.add(hotel)
    await db.commit()
    await db.refresh(hotel)
    return hotel


async def create_room(db: AsyncSession, data: dict) -> Room:
    room = Room(**data)
    db.add(room)
    await db.commit()
    await db.refresh(room)
    return room


async def get_all_room_rules(db: AsyncSession) -> List[RoomRule]:
    result = await db.execute(select(RoomRule).where(RoomRule.is_active == True))
    return result.scalars().all()


async def get_all_services(db: AsyncSession) -> List[AdditionalService]:
    result = await db.execute(select(AdditionalService).where(AdditionalService.is_active == True))
    return result.scalars().all()
