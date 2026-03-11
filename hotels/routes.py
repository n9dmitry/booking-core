# hotels/routes.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from hotels.schemas import HotelOut, RoomOut
from hotels.models import Hotel, Room

router = APIRouter(tags=["hotels"])


@router.get("/hotels", response_model=list[HotelOut])
async def list_hotels(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Hotel))
    hotels = result.scalars().all()
    return hotels


@router.get("/hotels/{hotel_id}", response_model=HotelOut)
async def get_hotel(hotel_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Hotel).where(Hotel.id == hotel_id))
    hotel = result.scalar_one_or_none()
    if not hotel:
        raise HTTPException(status_code=404, detail="Отель не найден")
    return hotel


@router.get("/hotels/{hotel_id}/rooms", response_model=list[RoomOut])
async def list_rooms(hotel_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Room).where(Room.hotel_id == hotel_id))
    rooms = result.scalars().all()
    return rooms