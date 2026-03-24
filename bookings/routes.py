from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from database import get_db
from bookings import bookings as svc
from bookings.schemas import (
    BookingCalculateRequest, BookingCalculateResponse,
    BookingCreateRequest, BookingCreateResponse, BookingStatusResponse,
)
from utils import success_response, error_response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/booking", tags=["Booking"])


@router.post("/calculate", response_model=BookingCalculateResponse, summary="Расчёт стоимости")
async def calculate(req: BookingCalculateRequest, db: AsyncSession = Depends(get_db)):
    try:
        return await svc.calculate(db, req)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/create", response_model=BookingCreateResponse, status_code=201,
             summary="Создать бронь (ПД клиента уходят в Битрикс, в БД не хранятся)")
async def create(req: BookingCreateRequest, db: AsyncSession = Depends(get_db)):
    try:
        return await svc.create_booking(db, req)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception:
        logger.exception("Unexpected booking error")
        raise HTTPException(500, "Внутренняя ошибка сервера")


@router.get("/{booking_id}/status", response_model=BookingStatusResponse,
            summary="Статус брони (с lazy sync из Битрикс)")
async def status(booking_id: str, db: AsyncSession = Depends(get_db)):
    try:
        data = await svc.get_status(db, booking_id)
        return BookingStatusResponse(**data)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/{booking_id}/sync", summary="Принудительная синхронизация статуса из Битрикс24")
async def sync_status(booking_id: str, db: AsyncSession = Depends(get_db)):
    """
    Вручную запрашивает Битрикс24 о текущей стадии сделки и обновляет статус брони.
    Используется как fallback если webhook не настроен или пропустил событие.
    """
    try:
        new_status = await svc.sync_booking_status(db, booking_id)
        return success_response({"status": new_status}, "Синхронизация выполнена")
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/{booking_id}/cancel", summary="Отменить бронь")
async def cancel(booking_id: str, db: AsyncSession = Depends(get_db)):
    try:
        await svc.cancel_booking(db, booking_id)
        return success_response(None, "Бронь отменена")
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/webhook/bitrix/status",
             summary="Webhook от Битрикс24 — смена стадии сделки → обновление статуса брони")
async def bitrix_webhook(payload: dict, db: AsyncSession = Depends(get_db)):
    """
    Настройте в Битрикс24:
      Автоматизация → Роботы/Бизнес-процессы → при смене стадии сделки
      → HTTP-запрос на: POST https://your-domain/api/v1/booking/webhook/bitrix/status

    Ожидаемый payload (стандартный Bitrix outgoing webhook):
      {
        "data": {
          "FIELDS": {
            "ID": "123",
            "STAGE_ID": "WON"
          }
        }
      }

    Маппинг стадий → статусов настраивается в Админке → Настройки → Статусы Битрикс.
    """
    try:
        fields = payload.get("data", {}).get("FIELDS", {})
        # Битрикс шлёт ID как строку
        deal_id = int(fields.get("ID", 0))
        stage_id = str(fields.get("STAGE_ID", "")).strip()
        if deal_id and stage_id:
            await svc.process_bitrix_webhook(db, deal_id, stage_id)
            logger.info("Webhook обработан: deal_id=%d stage=%s", deal_id, stage_id)
        else:
            logger.warning("Webhook: пустой payload — %s", payload)
    except Exception as e:
        logger.exception("Webhook error: %s", e)
    # Всегда 200 чтобы Битрикс не повторял
    return {"status": "ok"}
