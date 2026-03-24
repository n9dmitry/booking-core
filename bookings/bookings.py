"""
Bookings domain — business logic.

Схема работы с Битрикс24:
  1. create_booking()     — создаёт контакт+сделку в Битрикс,
                            сохраняет в БД только: booking_id, room/hotel/dates,
                            цену, bitrix_contact_id, bitrix_deal_id, bitrix_deal_url.
                            ПД клиента в нашей БД НЕ хранятся.
  2. process_bitrix_webhook() — webhook от Битрикс меняет статус брони.
  3. sync_booking_status()    — ручной polling (fallback если webhook не пришёл).
  4. run_timeout_sweep()  — фоновая задача отмены просроченных броней.
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from bookings.models import Booking, BookingStatus, BookingStatusHistory, StatusMapping
from bookings.schemas import (
    BookingCalculateRequest, BookingCalculateResponse,
    BookingCreateRequest, BookingCreateResponse, ServiceBreakdown,
)
from bitrix.bitrix import BitrixClient
from captcha.captcha import verify_captcha
from hotels.models import AdditionalService, Room
from stock import stock as stock_svc
from config import settings
from utils import nights_count

logger = logging.getLogger(__name__)
bitrix = BitrixClient()


# ── Calculate ──────────────────────────────────────────────────────────────────

async def calculate(db: AsyncSession, req: BookingCalculateRequest) -> BookingCalculateResponse:
    room = await db.get(Room, req.room_id)
    if not room:
        raise ValueError("Номер не найден")

    nights = nights_count(req.check_in, req.check_out)
    room_total = room.base_price * nights
    breakdown = []
    services_total = 0.0

    for sr in req.services:
        svc = await db.get(AdditionalService, sr.id)
        if not svc or not svc.is_active:
            continue
        amount = (svc.price * nights * sr.quantity
                  if svc.charge_type == "per_night"
                  else svc.price * sr.quantity)
        breakdown.append(ServiceBreakdown(
            id=svc.id, name=svc.name, price=svc.price,
            quantity=sr.quantity, charge_type=svc.charge_type, amount=amount,
        ))
        services_total += amount

    return BookingCalculateResponse(
        nights=nights,
        room_price_per_night=room.base_price,
        room_total=room_total,
        services_breakdown=breakdown,
        services_total=services_total,
        total_amount=room_total + services_total,
    )


# ── Create ─────────────────────────────────────────────────────────────────────

async def create_booking(db: AsyncSession, req: BookingCreateRequest) -> BookingCreateResponse:
    # 1. Captcha
    if not await verify_captcha(req.captcha_token):
        raise ValueError("Неверная капча")

    # 2. Валидация дат
    if req.check_out < req.check_in:
        raise ValueError("Дата выезда не может быть раньше даты заезда")
    if req.check_in == req.check_out:
        raise ValueError("Дата заезда и выезда совпадают — минимум 1 ночь")

    # 3. Доступность
    if not await stock_svc.is_available(db, req.room_id, req.check_in, req.check_out):
        raise ValueError("Номер недоступен на выбранные даты")

    # 3. Расчёт стоимости
    calc = await calculate(db, req)

    # 4. Запись в БД — БЕЗ персональных данных клиента
    booking_id = str(uuid.uuid4())
    expires_at = datetime.utcnow() + timedelta(minutes=settings.BOOKING_TIMEOUT_MINUTES)

    booking = Booking(
        id=booking_id,
        hotel_id=req.hotel_id,
        room_id=req.room_id,
        check_in=req.check_in,
        check_out=req.check_out,
        adults=req.adults,
        children=req.children,
        room_total=calc.room_total,
        services_total=calc.services_total,
        total_amount=calc.total_amount,
        services_json=json.dumps([b.model_dump() for b in calc.services_breakdown]),
        status=BookingStatus.WAITING_PAYMENT,
        expires_at=expires_at,
    )
    db.add(booking)
    db.add(BookingStatusHistory(
        booking_id=booking_id,
        new_status=BookingStatus.WAITING_PAYMENT,
        comment="Бронь создана",
    ))
    await db.flush()

    # 5. Блокируем даты
    await stock_svc.block_dates(db, req.room_id, req.check_in, req.check_out, booking_id)
    await db.commit()

    # 6. Битрикс24 — создаём контакт + сделку
    #    ПД клиента уходят в Битрикс и больше нигде не хранятся
    payment_url = ""
    contact_id = None
    deal_id = None

    # Обогащаем req названиями отеля и номера для красивого заголовка сделки
    hotel_obj = await db.get(__import__('hotels.models', fromlist=['Hotel']).Hotel, req.hotel_id)
    room_obj  = await db.get(__import__('hotels.models', fromlist=['Room']).Room, req.room_id)
    req._hotel_name = hotel_obj.name if hotel_obj else req.hotel_id
    req._room_name  = f"{room_obj.number} — {room_obj.name}" if room_obj else str(req.room_id)

    try:
        result = await bitrix.create_deal(booking, req, calc)
        deal_id    = result["deal_id"]
        contact_id = result["contact_id"]

        booking.bitrix_deal_id  = deal_id
        booking.bitrix_deal_url = result["deal_url"]
        booking.bitrix_contact_id = contact_id

        await db.commit()
        payment_url = result["deal_url"]
        logger.info("Бронь %s → deal_id=%d contact_id=%d", booking_id, deal_id, contact_id)

    except Exception as e:
        logger.warning("Bitrix error (не критично, бронь сохранена): %s", e)

    return BookingCreateResponse(
        booking_id=booking_id,
        status=BookingStatus.WAITING_PAYMENT,
        expires_in=settings.BOOKING_TIMEOUT_MINUTES * 60,
        payment_url=payment_url,
        bitrix_deal_id=deal_id,
        bitrix_contact_id=contact_id,
    )


# ── Status ─────────────────────────────────────────────────────────────────────

async def get_status(db: AsyncSession, booking_id: str) -> dict:
    booking = await db.get(Booking, booking_id)
    if not booking:
        raise ValueError("Бронь не найдена")

    # Lazy timeout check
    if (booking.status == BookingStatus.WAITING_PAYMENT
            and booking.expires_at
            and datetime.utcnow() > booking.expires_at):
        await _do_timeout(db, booking)

    # Lazy sync с Битрикс (polling как fallback)
    if booking.status == BookingStatus.WAITING_PAYMENT and booking.bitrix_deal_id:
        try:
            await bitrix.sync_deal_status(db, booking)
        except Exception as e:
            logger.debug("sync_deal_status error (не критично): %s", e)

    expires_in = None
    if booking.status == BookingStatus.WAITING_PAYMENT and booking.expires_at:
        expires_in = max(0, int((booking.expires_at - datetime.utcnow()).total_seconds()))

    return {
        "booking_id": booking.id,
        "status": booking.status,
        "expires_in": expires_in,
        "bitrix_deal_url": booking.bitrix_deal_url,
    }


async def cancel_booking(db: AsyncSession, booking_id: str):
    booking = await db.get(Booking, booking_id)
    if not booking:
        raise ValueError("Бронь не найдена")
    if booking.status != BookingStatus.WAITING_PAYMENT:
        raise ValueError("Отмена доступна только до оплаты")
    await _set_status(db, booking, BookingStatus.CANCELLED, "Отменено клиентом")
    await stock_svc.release_dates(db, booking.room_id, booking.check_in, booking.check_out, booking.id)
    try:
        await bitrix.cancel_deal(booking.bitrix_deal_id, "Отменено клиентом")
    except Exception as e:
        logger.warning("Bitrix cancel: %s", e)


# ── Webhook от Битрикс24 ───────────────────────────────────────────────────────

async def process_bitrix_webhook(db: AsyncSession, deal_id: int, stage_id: str):
    """
    Обрабатывает входящий webhook от Битрикс24 при смене стадии сделки.
    Битрикс шлёт POST на /api/v1/booking/webhook/bitrix/status.

    Ожидаемый payload:
      { "data": { "FIELDS": { "ID": "123", "STAGE_ID": "WON" } } }

    Маппинг стадий настраивается в разделе "Настройки → Статусы Битрикс".
    """
    # Ищем маппинг стадии
    mapping_res = await db.execute(
        select(StatusMapping).where(StatusMapping.bitrix_stage_id == stage_id)
    )
    mapping = mapping_res.scalar_one_or_none()
    if not mapping:
        logger.warning("Webhook: нет маппинга для стадии '%s', deal_id=%d", stage_id, deal_id)
        return

    # Ищем бронь по deal_id
    booking_res = await db.execute(
        select(Booking).where(Booking.bitrix_deal_id == deal_id)
    )
    booking = booking_res.scalar_one_or_none()
    if not booking:
        logger.warning("Webhook: бронь с deal_id=%d не найдена", deal_id)
        return

    new_status = mapping.internal_status
    if booking.status == new_status:
        logger.debug("Webhook: статус уже %s, пропуск", new_status)
        return

    logger.info("Webhook: бронь %s %s → %s (deal_id=%d stage=%s)",
                booking.id, booking.status, new_status, deal_id, stage_id)

    await _set_status(db, booking, new_status, f"Bitrix webhook: {stage_id}")

    if new_status == BookingStatus.PAID:
        booking.expires_at = None
        await db.commit()
        asyncio.create_task(_send_confirmation(booking))

    elif new_status in (BookingStatus.CANCELLED, BookingStatus.CANCELLED_TIMEOUT):
        await stock_svc.release_dates(db, booking.room_id, booking.check_in, booking.check_out, booking.id)


# ── Ручная синхронизация статуса (polling) ────────────────────────────────────

async def sync_booking_status(db: AsyncSession, booking_id: str) -> Optional[str]:
    """
    Вручную запрашивает Битрикс о текущей стадии сделки и синхронизирует статус.
    Используется как fallback если webhook не настроен.
    Доступен через GET /api/v1/booking/{booking_id}/sync
    """
    booking = await db.get(Booking, booking_id)
    if not booking:
        raise ValueError("Бронь не найдена")
    if not booking.bitrix_deal_id:
        raise ValueError("Сделка Битрикс не привязана к этой брони")

    new_status = await bitrix.sync_deal_status(db, booking)
    return new_status or booking.status


# ── Background timeout sweep ───────────────────────────────────────────────────

async def run_timeout_sweep():
    """
    Фоновая задача — каждые 30 сек:
    1. Отменяет просроченные (expires_at < now) брони waiting_payment
    2. Синхронизирует статус активных броней с Битрикс24 (polling fallback)
    """
    from database import AsyncSessionLocal
    logger.info("Timeout sweep запущен")
    cycle = 0
    while True:
        await asyncio.sleep(30)
        cycle += 1
        try:
            async with AsyncSessionLocal() as db:
                # ── 1. Отменяем просроченные ──────────────────────────────
                result = await db.execute(
                    select(Booking).where(
                        and_(
                            Booking.status == BookingStatus.WAITING_PAYMENT,
                            Booking.expires_at < datetime.utcnow(),
                        )
                    )
                )
                expired = result.scalars().all()
                for b in expired:
                    logger.info("Timeout: бронь %s", b.id)
                    await _do_timeout(db, b)

                # ── 2. Каждые 5 минут (10 циклов × 30 сек) синхронизируем
                #       waiting_payment брони с Битрикс24 (если webhook молчит)
                if cycle % 10 == 0:
                    await _sync_waiting_with_bitrix(db)

        except Exception as e:
            logger.error("Timeout sweep error: %s", e)


async def _sync_waiting_with_bitrix(db):
    """
    Опрашивает Битрикс по всем waiting_payment бронам у которых есть deal_id.
    Если сделка уже в WON/LOSE — обновляем статус брони.
    """
    try:
        result = await db.execute(
            select(Booking).where(
                and_(
                    Booking.status == BookingStatus.WAITING_PAYMENT,
                    Booking.bitrix_deal_id != None,
                    Booking.expires_at > datetime.utcnow(),  # ещё не истёк
                )
            )
        )
        pending = result.scalars().all()
        if not pending:
            return

        logger.info("Bitrix sync: проверяем %d бронь(и)", len(pending))
        for b in pending:
            try:
                new_status = await bitrix.sync_deal_status(db, b)
                if new_status and new_status == BookingStatus.PAID:
                    logger.info("Bitrix sync: бронь %s помечена оплаченной", b.id)
            except Exception as e:
                logger.debug("Bitrix sync error для %s: %s", b.id, e)
    except Exception as e:
        logger.error("_sync_waiting_with_bitrix error: %s", e)


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _do_timeout(db: AsyncSession, booking: Booking):
    await _set_status(db, booking, BookingStatus.CANCELLED_TIMEOUT,
                      "Автоматическая отмена — таймаут оплаты")
    await stock_svc.release_dates(db, booking.room_id, booking.check_in, booking.check_out, booking.id)
    try:
        await bitrix.cancel_deal(
            booking.bitrix_deal_id,
            "Автоматическая отмена — время оплаты истекло"
        )
    except Exception as e:
        logger.warning("Bitrix timeout cancel: %s", e)
    asyncio.create_task(_send_timeout_email(booking))


async def _set_status(db: AsyncSession, booking: Booking, new_status: str, comment: str = ""):
    old = booking.status
    booking.status = new_status
    booking.updated_at = datetime.utcnow()
    db.add(BookingStatusHistory(
        booking_id=booking.id,
        old_status=old,
        new_status=new_status,
        comment=comment,
    ))
    await db.commit()


async def _send_confirmation(booking: Booking):
    """Email клиенту при оплате — данные берём из Битрикс."""
    try:
        from email_service import send_email
        from utils import format_date_ru
        # email клиента не хранится в нашей БД — берём из Битрикс
        contact = await _get_contact_email(booking.bitrix_contact_id)
        if not contact:
            logger.warning("Не удалось получить email контакта для брони %s", booking.id)
            return
        await send_email(
            to=contact["email"],
            subject=f"Бронирование подтверждено — #{booking.id[:8].upper()}",
            html=(
                f"<h2>Бронирование подтверждено!</h2>"
                f"<p>Здравствуйте, <b>{contact.get('name','')}</b>!</p>"
                f"<p>Оплата прошла успешно. Номер брони: <b>{booking.id[:8].upper()}</b></p>"
                f"<p>Заезд: {format_date_ru(booking.check_in)} — Выезд: {format_date_ru(booking.check_out)}</p>"
                f"<p>Сумма: <b>{booking.total_amount:,.0f} ₽</b></p>"
            ),
        )
    except Exception as e:
        logger.warning("Email confirmation error: %s", e)


async def _send_timeout_email(booking: Booking):
    try:
        from email_service import send_email
        contact = await _get_contact_email(booking.bitrix_contact_id)
        if not contact:
            return
        await send_email(
            to=contact["email"],
            subject="Бронь отменена — время оплаты истекло",
            html=(
                f"<h2>Бронирование отменено</h2>"
                f"<p>Здравствуйте, <b>{contact.get('name','')}</b>!</p>"
                f"<p>Время оплаты истекло. Повторите бронирование на сайте.</p>"
            ),
        )
    except Exception as e:
        logger.warning("Email timeout error: %s", e)


async def _get_contact_email(contact_id: Optional[int]) -> Optional[dict]:
    """Получает email и имя контакта из Битрикс24."""
    if not contact_id:
        return None
    try:
        res = await bitrix._call("crm.contact.get", {
            "id": contact_id,
            "select": ["NAME", "LAST_NAME", "EMAIL"],
        })
        emails = res.get("EMAIL", [])
        email = emails[0]["VALUE"] if emails else None
        if not email:
            return None
        name = f"{res.get('NAME','')} {res.get('LAST_NAME','')}".strip()
        return {"email": email, "name": name}
    except Exception as e:
        logger.warning("_get_contact_email %d: %s", contact_id, e)
        return None


# Fix Optional import at top level
from typing import Optional
