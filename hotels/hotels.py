# hotels/hotels.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hotels.models import Hotel, Room


async def get_hotel_by_id(db: AsyncSession, hotel_id: str) -> Hotel | None:
    result = await db.execute(
        select(Hotel).where(Hotel.id == hotel_id)
    )
    return result.scalar_one_or_none()


async def get_rooms_by_hotel(db: AsyncSession, hotel_id: str) -> list[Room]:
    result = await db.execute(
        select(Room).where(Room.hotel_id == hotel_id)
    )
    return result.scalars().all()