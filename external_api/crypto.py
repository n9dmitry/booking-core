"""
Шифрование персональных данных гостей.

Данные гостя (ФИО, телефон, email, паспорт) шифруются симметрично (Fernet/AES-128)
перед тем как покинуть сайт отеля. Расшифровка происходит только в момент
создания контакта/сделки в Битрикс24 — нигде не хранятся в открытом виде.

Ключ GUEST_DATA_KEY генерируется один раз:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
и прописывается в .env обоих проектов.
"""
import json
import base64
from typing import Any
from cryptography.fernet import Fernet, InvalidToken
from config import settings


def _get_fernet() -> Fernet:
    key = settings.GUEST_DATA_KEY
    if not key:
        raise RuntimeError(
            "GUEST_DATA_KEY не задан в .env. "
            "Сгенерируй ключ: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_guest(data: dict) -> str:
    """
    Шифрует dict с данными гостя → возвращает base64-строку.
    Используется на стороне сайта перед отправкой в бэкенд.
    """
    raw = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
    return _get_fernet().encrypt(raw).decode("utf-8")


def decrypt_guest(token: str) -> dict:
    """
    Расшифровывает зашифрованные данные гостя → dict.
    Используется в бэкенде перед отправкой в Битрикс24.
    """
    try:
        raw = _get_fernet().decrypt(token.encode("utf-8"))
        return json.loads(raw.decode("utf-8"))
    except InvalidToken:
        raise ValueError("Не удалось расшифровать данные гостя — неверный ключ или повреждённые данные")
    except Exception as e:
        raise ValueError(f"Ошибка расшифровки: {e}")


def is_encrypted(value: str) -> bool:
    """Проверяет похоже ли значение на зашифрованные данные (Fernet token)."""
    try:
        decoded = base64.urlsafe_b64decode(value + "==")
        return decoded[:1] == b'\x80'  # Fernet magic byte
    except Exception:
        return False
