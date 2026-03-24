from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date, timedelta
from typing import AsyncGenerator
import asyncio
import json

from database import get_db
from stock import stock as svc
from stock.schemas import AvailabilityOut
from utils import success_response

router = APIRouter(prefix="/rooms", tags=["Stock"])


@router.get("/{room_id}/availability", summary="Календарь занятости номера")
async def get_availability(
    room_id: int,
    from_date: date = Query(default=None),
    to_date: date = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not from_date:
        from_date = date.today()
    if not to_date:
        to_date = from_date + timedelta(days=90)

    blocked = await svc.get_blocked_dates(db, room_id, from_date, to_date)
    return success_response(AvailabilityOut(
        room_id=room_id,
        from_date=str(from_date),
        to_date=str(to_date),
        blocked_dates=blocked,
    ).model_dump())


@router.get("/{room_id}/availability/stream", summary="Live-поток обновлений доступности (SSE)")
async def stream_availability(room_id: int):
    """
    Server-Sent Events — фронтенд подписывается и получает обновления в реальном времени.
    Подключение: new EventSource('/rooms/{id}/availability/stream')
    """
    async def generator() -> AsyncGenerator[str, None]:
        yield f"data: {json.dumps({'type': 'connected', 'room_id': room_id})}\n\n"
        # Heartbeat loop — реальные события публикуются из bookings.bookings через notify_availability
        while True:
            await asyncio.sleep(15)
            yield ": heartbeat\n\n"

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# Internal helper used by bookings domain to push SSE events
_sse_queues: dict[int, list] = {}


def get_sse_queues():
    return _sse_queues


async def notify_availability(room_id: int, payload: dict):
    """Push availability update to all SSE subscribers of this room."""
    queues = _sse_queues.get(room_id, [])
    for q in queues:
        await q.put(payload)
