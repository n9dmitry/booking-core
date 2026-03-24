from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import date

from database import get_db
from hotels import hotels as svc
from hotels.schemas import HotelOut, RoomOut, RoomRuleOut, ServiceOut
from utils import success_response

router = APIRouter(prefix="/hotels", tags=["Hotels"])


@router.get("", summary="Список всех отелей")
async def list_hotels(db: AsyncSession = Depends(get_db)):
    items = await svc.get_all_hotels(db)
    return success_response([HotelOut.model_validate(h).model_dump() for h in items])


@router.get("/{hotel_id}", summary="Информация об отеле")
async def get_hotel(hotel_id: str, db: AsyncSession = Depends(get_db)):
    hotel = await svc.get_hotel(db, hotel_id)
    if not hotel or not hotel.is_active:
        raise HTTPException(404, "Отель не найден")
    return success_response(HotelOut.model_validate(hotel).model_dump())


@router.get("/{hotel_id}/rooms", summary="Номера отеля (с фильтром по датам)")
async def get_rooms(
    hotel_id: str,
    check_in: Optional[date] = Query(None),
    check_out: Optional[date] = Query(None),
    adults: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    items = await svc.get_hotel_rooms(db, hotel_id, check_in, check_out, adults)
    result = []
    for item in items:
        room_data = RoomOut.model_validate(item["room"]).model_dump()
        room_data["rules"] = [RoomRuleOut.model_validate(r).model_dump() for r in item["rules"]]
        result.append(room_data)
    return success_response(result)


@router.get("/{hotel_id}/services", summary="Дополнительные услуги отеля")
async def get_services(hotel_id: str, db: AsyncSession = Depends(get_db)):
    items = await svc.get_hotel_services(db, hotel_id)
    return success_response([ServiceOut.model_validate(s).model_dump() for s in items])
