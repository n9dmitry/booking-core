"""
Внешний API для сайтов отелей.
Аутентификация: Bearer {token} — токен из /admin/api-tokens

  GET  /ext/hotel
  GET  /ext/rooms/available?check_in=&check_out=&adults=&children=
  GET  /ext/rooms/{room_id}
  POST /ext/booking
  GET  /ext/booking/{booking_id}
  DELETE /ext/booking/{booking_id}
"""
import json, uuid, logging
from datetime import datetime, date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from external_api.auth import get_token_record
from external_api.models import HotelApiToken
from external_api.schemas import RoomOut, HotelOut, BookingOut, BookingStatusOut, BookingRequest
from external_api.crypto import decrypt_guest
from hotels.models import Hotel, Room
from bookings.models import Booking, BookingStatus, BookingStatusHistory
from stock import stock as stock_svc
from config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ext", tags=["External API — Сайт отеля"])


def _ok(data, message="OK"):
    return {"status": "success", "data": data, "message": message}

def _nights(ci, co):
    return max((co - ci).days, 1)

def _room_out(room, check_in, check_out, available):
    nights = _nights(check_in, check_out)
    photos = []
    if room.photos:
        try: photos = json.loads(room.photos)
        except: pass
    return RoomOut(
        id=room.id, hotel_id=room.hotel_id, number=room.number, name=room.name,
        description=room.description, capacity_adults=room.capacity_adults,
        capacity_children=room.capacity_children, base_price=room.base_price,
        price_for_stay=round(room.base_price * nights, 2), nights=nights,
        area_sqm=room.area_sqm, floor=room.floor, photos=photos, is_available=available,
    ).model_dump()

def _booking_out(booking, source=None, message=""):
    return BookingOut(
        booking_id=booking.id, status=booking.status,
        hotel_id=booking.hotel_id, room_id=booking.room_id,
        check_in=booking.check_in, check_out=booking.check_out,
        adults=booking.adults, children=booking.children,
        total_amount=booking.total_amount,
        expires_at=booking.expires_at.isoformat() if booking.expires_at else None,
        source=source, message=message,
    ).model_dump()

async def _create_booking(db, hotel_id, room, check_in, check_out, adults, children, guest_data, source, comment):
    nights = _nights(check_in, check_out)
    room_total = room.base_price * nights
    booking_id = str(uuid.uuid4())
    expires_at = datetime.utcnow() + timedelta(minutes=settings.BOOKING_TIMEOUT_MINUTES)

    booking = Booking(
        id=booking_id, hotel_id=hotel_id, room_id=room.id,
        check_in=check_in, check_out=check_out, adults=adults, children=children,
        room_total=room_total, services_total=0, total_amount=room_total,
        services_json="[]", status=BookingStatus.WAITING_PAYMENT, expires_at=expires_at,
    )
    db.add(booking)
    db.add(BookingStatusHistory(
        booking_id=booking_id, new_status=BookingStatus.WAITING_PAYMENT,
        comment=f"Создана через API. Источник: {source or 'не указан'}",
    ))
    await db.flush()
    await stock_svc.block_dates(db, room.id, check_in, check_out, booking_id)
    await db.flush()

    try:
        from bitrix.bitrix import BitrixClient
        from bookings.schemas import BookingCalculateResponse
        p = guest_data.get("passport") or {}
        req_obj = type("R", (), {
            "guest_full_name": guest_data.get("full_name", ""),
            "guest_birth_date": date.fromisoformat(guest_data["birth_date"]) if guest_data.get("birth_date") else None,
            "guest_phone": guest_data.get("phone", ""),
            "guest_email": guest_data.get("email", ""),
            "comment": f"[{source}] {comment}" if source and comment else (comment or source or ""),
            "passport_series": p.get("series", ""), "passport_number": p.get("number", ""),
            "passport_issued_by": p.get("issued_by", ""),
            "passport_issued_date": date.fromisoformat(p["issued_date"]) if p.get("issued_date") else None,
            "check_in": check_in, "check_out": check_out,
            "adults": adults, "children": children,
            "hotel_id": hotel_id, "room_id": room.id, "services": [],
        })()
        calc = BookingCalculateResponse(nights=nights, room_price_per_night=room.base_price,
            room_total=room_total, services_breakdown=[], services_total=0, total_amount=room_total)
        result = await BitrixClient().create_deal(booking, req_obj, calc)
        booking.bitrix_deal_id    = result["deal_id"]
        booking.bitrix_deal_url   = result["deal_url"]
        booking.bitrix_contact_id = result.get("contact_id")
    except Exception as e:
        logger.warning("Bitrix error: %s", e)
    return booking


@router.get("/hotel", summary="Данные отеля")
async def get_hotel(token: HotelApiToken = Depends(get_token_record), db: AsyncSession = Depends(get_db)):
    hotel = await db.get(Hotel, token.hotel_id)
    if not hotel or not hotel.is_active:
        raise HTTPException(404, "Отель не найден")
    return _ok(HotelOut(id=hotel.id, name=hotel.name, address=hotel.address,
        description=hotel.description, phone=hotel.phone, email=hotel.email,
        check_in_time=hotel.check_in_time, check_out_time=hotel.check_out_time,
        rules_html=hotel.rules_html).model_dump())


@router.get("/rooms", summary="Все номера отеля (без фильтра дат)")
async def get_all_rooms(
    token: HotelApiToken = Depends(get_token_record), db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Room).where(Room.hotel_id == token.hotel_id, Room.is_active == True))
    rooms = result.scalars().all()
    today = date.today()
    tomorrow = today + timedelta(days=1)
    out = [_room_out(room, today, tomorrow, True) for room in rooms]
    return _ok(out, f"Номеров: {len(out)}")


@router.get("/rooms/available", summary="Доступные номера")
async def get_available_rooms(
    check_in: date, check_out: date, adults: int = 1, children: int = 0,
    token: HotelApiToken = Depends(get_token_record), db: AsyncSession = Depends(get_db),
):
    if check_out <= check_in:
        raise HTTPException(400, "Дата выезда должна быть позже даты заезда")
    result = await db.execute(select(Room).where(Room.hotel_id == token.hotel_id, Room.is_active == True))
    rooms = result.scalars().all()
    out = []
    for room in rooms:
        available = await stock_svc.is_available(db, room.id, check_in, check_out)
        fits = room.capacity_adults >= adults and (children == 0 or room.capacity_children >= children)
        out.append({**_room_out(room, check_in, check_out, available), "fits_occupancy": fits})
    return _ok(out, f"Номеров: {len(out)}, доступных: {sum(1 for r in out if r['is_available'])}")


@router.get("/rooms/{room_id}", summary="Данные номера")
async def get_room(
    room_id: int, check_in: Optional[date] = None, check_out: Optional[date] = None,
    token: HotelApiToken = Depends(get_token_record), db: AsyncSession = Depends(get_db),
):
    room = await db.get(Room, room_id)
    if not room or room.hotel_id != token.hotel_id or not room.is_active:
        raise HTTPException(404, "Номер не найден")
    ci = check_in or date.today()
    co = check_out or (ci + timedelta(days=1))
    return _ok(_room_out(room, ci, co, await stock_svc.is_available(db, room.id, ci, co)))


@router.post("/booking", summary="Создать бронирование")
async def create_booking(
    req: BookingRequest,
    token: HotelApiToken = Depends(get_token_record), db: AsyncSession = Depends(get_db),
):
    if req.check_out <= req.check_in:
        raise HTTPException(400, "Дата выезда должна быть позже даты заезда")
    try:
        guest_data = decrypt_guest(req.guest_data_encrypted)
    except ValueError as e:
        raise HTTPException(400, str(e))

    source = req.source or token.label or f"API токен #{token.id}"
    occ = req.occupancy

    if occ.adult_room_id and occ.child_room_id:
        ar = await db.get(Room, occ.adult_room_id)
        cr = await db.get(Room, occ.child_room_id)
        if not ar or ar.hotel_id != token.hotel_id: raise HTTPException(404, "Взрослый номер не найден")
        if not cr or cr.hotel_id != token.hotel_id: raise HTTPException(404, "Детский номер не найден")
        if not await stock_svc.is_available(db, ar.id, req.check_in, req.check_out):
            raise HTTPException(409, f"Номер #{ar.number} недоступен")
        if not await stock_svc.is_available(db, cr.id, req.check_in, req.check_out):
            raise HTTPException(409, f"Номер #{cr.number} недоступен")
        ab = await _create_booking(db, token.hotel_id, ar, req.check_in, req.check_out, occ.adults, 0, guest_data, source, req.comment)
        cb = await _create_booking(db, token.hotel_id, cr, req.check_in, req.check_out, 0, occ.children, guest_data, source, req.comment)
        await db.commit()
        return _ok({"adult_booking": _booking_out(ab), "child_booking": _booking_out(cb),
            "total_amount": ab.total_amount + cb.total_amount, "source": source}, "Создано 2 брони")

    if not req.room_id:
        raise HTTPException(400, "Укажите room_id")
    room = await db.get(Room, req.room_id)
    if not room or room.hotel_id != token.hotel_id or not room.is_active:
        raise HTTPException(404, "Номер не найден")
    if not await stock_svc.is_available(db, room.id, req.check_in, req.check_out):
        raise HTTPException(409, f"Номер #{room.number} недоступен")
    booking = await _create_booking(db, token.hotel_id, room, req.check_in, req.check_out,
        occ.adults, occ.children, guest_data, source, req.comment)
    await db.commit()
    return _ok(_booking_out(booking, source, f"Номер забронирован. Ожидает оплаты {settings.BOOKING_TIMEOUT_MINUTES} мин."), "Бронирование создано")


@router.get("/booking/{booking_id}", summary="Статус брони")
async def get_booking_status(
    booking_id: str, token: HotelApiToken = Depends(get_token_record), db: AsyncSession = Depends(get_db),
):
    booking = await db.get(Booking, booking_id)
    if not booking or booking.hotel_id != token.hotel_id:
        raise HTTPException(404, "Бронь не найдена")
    active = {BookingStatus.WAITING_PAYMENT, BookingStatus.PAID, BookingStatus.CHECKED_IN}
    return _ok(BookingStatusOut(booking_id=booking.id, status=booking.status,
        is_active=booking.status in active,
        expires_at=booking.expires_at.isoformat() if booking.expires_at else None,
        room_id=booking.room_id, hotel_id=booking.hotel_id,
        check_in=booking.check_in, check_out=booking.check_out, source=token.label).model_dump())



@router.post("/encrypt-guest", summary="Зашифровать данные гостя (браузер → сервер)")
async def encrypt_guest_endpoint(
    request: Request,
    token: HotelApiToken = Depends(get_token_record),
):
    """
    Принимает JSON с данными гостя, возвращает Fernet-токен.
    Вызывается из браузера перед созданием брони.
    """
    from external_api.crypto import encrypt_guest
    data = await request.json()
    encrypted = encrypt_guest(data)
    return {"token": encrypted}

@router.delete("/booking/{booking_id}", summary="Отменить бронь")
async def cancel_booking(
    booking_id: str, token: HotelApiToken = Depends(get_token_record), db: AsyncSession = Depends(get_db),
):
    booking = await db.get(Booking, booking_id)
    if not booking or booking.hotel_id != token.hotel_id:
        raise HTTPException(404, "Бронь не найдена")
    if booking.status != BookingStatus.WAITING_PAYMENT:
        raise HTTPException(400, f"Нельзя отменить бронь со статусом «{booking.status}»")
    old = booking.status
    booking.status = BookingStatus.CANCELLED
    booking.updated_at = datetime.utcnow()
    db.add(BookingStatusHistory(booking_id=booking_id, old_status=old,
        new_status=BookingStatus.CANCELLED, comment=f"Отменена клиентом [{token.label or token.id}]"))
    try:
        await stock_svc.release_dates(db, booking.room_id, booking.check_in, booking.check_out, booking_id)
    except Exception as e:
        logger.warning("release_dates: %s", e)
    if booking.bitrix_deal_id:
        try:
            from bitrix.bitrix import BitrixClient
            await BitrixClient().cancel_deal(booking.bitrix_deal_id, "Отменена клиентом")
        except Exception as e:
            logger.warning("Bitrix cancel: %s", e)
    await db.commit()
    return _ok({"booking_id": booking_id, "status": "cancelled"}, "Бронь отменена")
