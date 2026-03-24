"""
Stock (availability) service.

Логика проверки доступности номера:

1. Таблица rooms_availability — основной источник.
   Дата заблокирована если есть запись с is_blocked=True.

2. Дополнительная проверка по таблице bookings — страховка:
   Ищем активные брони на этот номер и эти даты со статусами:
     - waiting_payment  (ещё не оплачено, но 20 мин ещё не прошло)
     - paid
     - checked_in
   Если такая бронь есть — номер недоступен, даже если rooms_availability пустой.

3. Истёкшие waiting_payment (expires_at < now) считаются отменёнными
   и НЕ блокируют номер.

4. При удалении брони из админки — явно освобождаем даты.
"""
from datetime import date, datetime
from typing import List, Optional
from sqlalchemy import select, and_, delete, or_
from sqlalchemy.ext.asyncio import AsyncSession

from stock.models import RoomAvailability
from utils import dates_in_range


async def is_available(
    db: AsyncSession,
    room_id: int,
    check_in: date,
    check_out: date,
    exclude_booking_id: Optional[str] = None,
) -> bool:
    """
    Возвращает True если номер свободен на все даты [check_in, check_out).

    Проверяет ДВА источника:
      1. rooms_availability — основная таблица блокировок
      2. bookings — активные брони (страховка от race condition и ошибок)
    """
    needed = dates_in_range(check_in, check_out)
    if not needed:
        return False

    # ── Проверка 1: таблица rooms_availability ─────────────────────────────
    q = select(RoomAvailability).where(
        and_(
            RoomAvailability.room_id == room_id,
            RoomAvailability.date.in_(needed),
            RoomAvailability.is_blocked == True,
        )
    )
    if exclude_booking_id:
        q = q.where(RoomAvailability.booking_id != exclude_booking_id)

    result = await db.execute(q)
    blocked = result.scalars().first()
    if blocked:
        return False

    # ── Проверка 2: таблица bookings (страховка) ───────────────────────────
    # Ищем пересекающиеся активные брони
    # Пересечение: booking.check_in < check_out AND booking.check_out > check_in
    from bookings.models import Booking, BookingStatus

    active_statuses = [
        BookingStatus.WAITING_PAYMENT,
        BookingStatus.PAID,
        BookingStatus.CHECKED_IN,
    ]

    q2 = select(Booking).where(
        and_(
            Booking.room_id == room_id,
            Booking.status.in_(active_statuses),
            Booking.check_in < check_out,
            Booking.check_out > check_in,
        )
    )
    if exclude_booking_id:
        q2 = q2.where(Booking.id != exclude_booking_id)

    result2 = await db.execute(q2)
    conflicts = result2.scalars().all()

    now = datetime.utcnow()
    for b in conflicts:
        if b.status == BookingStatus.WAITING_PAYMENT:
            # Проверяем не истёк ли таймаут
            if b.expires_at and now > b.expires_at:
                # Таймаут истёк — эта бронь не блокирует
                # (sweep задача сама её отменит, но не блокируем нового клиента)
                continue
        # Активная бронь — номер занят
        return False

    return True


async def get_blocked_dates(
    db: AsyncSession, room_id: int, from_date: date, to_date: date
) -> List[str]:
    """Возвращает список заблокированных дат в диапазоне."""
    result = await db.execute(
        select(RoomAvailability).where(
            and_(
                RoomAvailability.room_id == room_id,
                RoomAvailability.date >= from_date,
                RoomAvailability.date <= to_date,
                RoomAvailability.is_blocked == True,
            )
        )
    )
    return [str(r.date) for r in result.scalars().all()]


async def block_dates(
    db: AsyncSession, room_id: int, check_in: date, check_out: date, booking_id: str
):
    """
    Блокирует даты в rooms_availability.
    Если запись уже существует (race condition) — обновляем booking_id.
    """
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    for d in dates_in_range(check_in, check_out):
        # Используем INSERT OR REPLACE для idempotency
        existing = await db.execute(
            select(RoomAvailability).where(
                and_(
                    RoomAvailability.room_id == room_id,
                    RoomAvailability.date == d,
                )
            )
        )
        row = existing.scalars().first()
        if row:
            # Уже заблокировано — обновляем booking_id
            row.booking_id = booking_id
            row.is_blocked = True
        else:
            db.add(RoomAvailability(
                room_id=room_id,
                date=d,
                booking_id=booking_id,
                is_blocked=True,
            ))

    await db.commit()


async def release_dates(
    db: AsyncSession, room_id: int, check_in: date, check_out: date,
    booking_id: Optional[str] = None,
):
    """
    Освобождает даты в rooms_availability.
    Если указан booking_id — удаляем только записи этой брони.
    """
    needed = dates_in_range(check_in, check_out)
    q = delete(RoomAvailability).where(
        and_(
            RoomAvailability.room_id == room_id,
            RoomAvailability.date.in_(needed),
        )
    )
    if booking_id:
        q = q.where(RoomAvailability.booking_id == booking_id)

    await db.execute(q)
    await db.commit()
