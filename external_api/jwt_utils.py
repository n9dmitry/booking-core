"""
JWT-утилиты для клиентских токенов бронирований.

Схема:
  POST /ext/booking           → создаёт бронь → возвращает booking_token (JWT)
  GET  /ext/my/booking        → статус своей брони (только по booking_token)
  DELETE /ext/my/booking      → отменить свою бронь (только по booking_token)

Payload JWT:
  {
    "sub": "<booking_id>",       # ID брони
    "hotel_id": "<hotel_id>",    # для дополнительной проверки
    "type": "booking_access",    # тип токена
    "exp": <unix_timestamp>      # истекает через BOOKING_TOKEN_TTL_DAYS дней
  }
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt, JWTError
from fastapi import HTTPException, Header
from config import settings

ALGORITHM = "HS256"
BOOKING_TOKEN_TTL_DAYS = 30   # токен действует 30 дней


def create_booking_token(booking_id: str, hotel_id: str) -> str:
    """Создаёт JWT для клиента после успешного бронирования."""
    expire = datetime.now(timezone.utc) + timedelta(days=BOOKING_TOKEN_TTL_DAYS)
    payload = {
        "sub":      booking_id,
        "hotel_id": hotel_id,
        "type":     "booking_access",
        "exp":      expire,
        "iat":      datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_booking_token(token: str) -> dict:
    """
    Декодирует и валидирует JWT клиента.
    Возвращает payload или бросает HTTPException 401.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as e:
        raise HTTPException(
            status_code=401,
            detail=f"Недействительный токен брони: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "booking_access":
        raise HTTPException(401, "Неверный тип токена")

    return payload


def require_booking_token(authorization: str = Header(...)) -> dict:
    """
    FastAPI dependency — извлекает booking_token из заголовка Authorization.
    Использование: payload = Depends(require_booking_token)
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Требуется заголовок Authorization: Bearer <booking_token>")
    token = authorization.removeprefix("Bearer ").strip()
    return decode_booking_token(token)
