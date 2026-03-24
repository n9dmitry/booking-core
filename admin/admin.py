"""Admin panel business logic — CRUD for all entities."""
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from hotels.models import Hotel, Room, RoomRule, AdditionalService, HotelService, RoomRuleLink
from bookings.models import Booking, StatusMapping
from stock.models import RoomAvailability


# ─── Hotels ───────────────────────────────────────────────────────────────────

async def list_hotels(db: AsyncSession):
    r = await db.execute(select(Hotel))
    return r.scalars().all()

async def get_hotel(db: AsyncSession, hotel_id: str):
    return await db.get(Hotel, hotel_id)

async def save_hotel(db: AsyncSession, data: dict):
    hotel = await db.get(Hotel, data["id"])
    if hotel:
        for k, v in data.items():
            setattr(hotel, k, v)
    else:
        hotel = Hotel(**data)
        db.add(hotel)
    await db.commit()
    return hotel

async def delete_hotel(db: AsyncSession, hotel_id: str):
    hotel = await db.get(Hotel, hotel_id)
    if hotel:
        await db.delete(hotel)
        await db.commit()


# ─── Rooms ────────────────────────────────────────────────────────────────────

async def list_rooms(db: AsyncSession, hotel_id: Optional[str] = None):
    q = select(Room)
    if hotel_id:
        q = q.where(Room.hotel_id == hotel_id)
    r = await db.execute(q)
    return r.scalars().all()

async def get_room(db: AsyncSession, room_id: int):
    return await db.get(Room, room_id)

async def save_room(db: AsyncSession, data: dict, rule_ids: list = None):
    room_id = data.pop("id", None)
    room = await db.get(Room, room_id) if room_id else None
    if room:
        for k, v in data.items():
            setattr(room, k, v)
    else:
        room = Room(**data)
        db.add(room)
    await db.flush()

    if rule_ids is not None:
        await db.execute(delete(RoomRuleLink).where(RoomRuleLink.room_id == room.id))
        for rid in rule_ids:
            db.add(RoomRuleLink(room_id=room.id, rule_id=int(rid)))

    await db.commit()
    return room

async def delete_room(db: AsyncSession, room_id: int):
    room = await db.get(Room, room_id)
    if room:
        await db.delete(room)
        await db.commit()


# ─── Room Rules ───────────────────────────────────────────────────────────────

async def list_rules(db: AsyncSession):
    r = await db.execute(select(RoomRule))
    return r.scalars().all()

async def save_rule(db: AsyncSession, data: dict):
    rule_id = data.pop("id", None)
    rule = await db.get(RoomRule, int(rule_id)) if rule_id else None
    if rule:
        for k, v in data.items():
            setattr(rule, k, v)
    else:
        rule = RoomRule(**data)
        db.add(rule)
    await db.commit()
    return rule

async def delete_rule(db: AsyncSession, rule_id: int):
    rule = await db.get(RoomRule, rule_id)
    if rule:
        await db.delete(rule)
        await db.commit()


# ─── Services ─────────────────────────────────────────────────────────────────

async def list_services(db: AsyncSession):
    r = await db.execute(select(AdditionalService))
    return r.scalars().all()

async def save_service(db: AsyncSession, data: dict):
    svc = await db.get(AdditionalService, data["id"])
    if svc:
        for k, v in data.items():
            setattr(svc, k, v)
    else:
        svc = AdditionalService(**data)
        db.add(svc)
    await db.commit()
    return svc

async def delete_service(db: AsyncSession, service_id: str):
    svc = await db.get(AdditionalService, service_id)
    if svc:
        await db.delete(svc)
        await db.commit()


# ─── Status Mappings ──────────────────────────────────────────────────────────

async def list_mappings(db: AsyncSession):
    r = await db.execute(select(StatusMapping))
    return r.scalars().all()

async def save_mapping(db: AsyncSession, internal: str, bitrix_stage: str, desc: str = ""):
    r = await db.execute(select(StatusMapping).where(StatusMapping.internal_status == internal))
    m = r.scalar_one_or_none()
    if m:
        m.bitrix_stage_id = bitrix_stage
        m.description = desc
    else:
        db.add(StatusMapping(internal_status=internal, bitrix_stage_id=bitrix_stage, description=desc))
    await db.commit()


# ─── Bookings ─────────────────────────────────────────────────────────────────

async def list_bookings(db: AsyncSession, status: Optional[str] = None,
                        hotel_id: Optional[str] = None, limit: int = 100):
    q = select(Booking).order_by(Booking.created_at.desc()).limit(limit)
    if status:
        q = q.where(Booking.status == status)
    if hotel_id:
        q = q.where(Booking.hotel_id == hotel_id)
    r = await db.execute(q)
    return r.scalars().all()

async def get_booking(db: AsyncSession, booking_id: str):
    return await db.get(Booking, booking_id)
