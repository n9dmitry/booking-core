"""
Bitrix24 REST API client.

Webhook URL (входящий, уже настроен):
  https://b24-s16x3l.bitrix24.ru/rest/1/e20ldvdl6miys2ow/

Что создаётся в Битрикс при бронировании:
  1. Контакт (find_or_create_contact) — поиск по email/телефону, иначе создание
  2. Сделка (create_deal) — полные данные брони + ссылка на бронь в админке
  3. Счёт (create_invoice) — сумма к оплате

Webhook → статусы (входящий от Битрикс):
  POST /api/v1/booking/webhook/bitrix/status
  payload: {"data": {"FIELDS": {"ID": "123", "STAGE_ID": "WON"}}}
"""
import logging
from typing import Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)


class BitrixClient:

    def __init__(self):
        self.domain = settings.BITRIX24_DOMAIN
        self.token = settings.BITRIX24_WEBHOOK_TOKEN
        self.timeout = httpx.Timeout(30.0)

    @property
    def base_url(self) -> str:
        return f"https://{self.domain}/rest/{self.token}"

    def _is_configured(self) -> bool:
        return bool(self.domain and self.token)

    # ── Низкоуровневый вызов ──────────────────────────────────────────────────

    async def _call(self, method: str, params: dict) -> dict:
        if not self._is_configured():
            logger.warning("Bitrix24 не настроен, пропуск вызова %s", method)
            return {}

        url = f"{self.base_url}/{method}.json"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(3):
                try:
                    resp = await client.post(url, json=params)
                    resp.raise_for_status()
                    data = resp.json()
                    if "error" in data:
                        raise ValueError(
                            f"Bitrix [{method}]: "
                            f"{data.get('error_description', data['error'])}"
                        )
                    return data.get("result", {})
                except httpx.TimeoutException:
                    if attempt == 2:
                        raise
                    logger.warning("Bitrix timeout, попытка %d/3", attempt + 1)
        return {}

    # ── Контакт ───────────────────────────────────────────────────────────────

    async def find_or_create_contact(
        self,
        full_name: str,
        email: str,
        phone: str,
        birth_date: str = "",
        passport: Optional[dict] = None,
    ) -> int:
        """
        Ищет контакт по email, затем по телефону.
        Если не найден — создаёт новый.
        Возвращает Bitrix contact ID.
        """
        # 1. Поиск по email
        res = await self._call("crm.contact.list", {
            "filter": {"EMAIL": email},
            "select": ["ID"],
        })
        if res:
            cid = int(res[0]["ID"])
            logger.info("Bitrix: найден контакт по email id=%d", cid)
            return cid

        # 2. Поиск по телефону
        res = await self._call("crm.contact.list", {
            "filter": {"PHONE": phone},
            "select": ["ID"],
        })
        if res:
            cid = int(res[0]["ID"])
            logger.info("Bitrix: найден контакт по телефону id=%d", cid)
            return cid

        # 3. Создание нового контакта
        parts = full_name.strip().split()
        fields = {
            "LAST_NAME":   parts[0] if len(parts) > 0 else full_name,
            "NAME":        parts[1] if len(parts) > 1 else "",
            "SECOND_NAME": parts[2] if len(parts) > 2 else "",
            "BIRTHDATE":   birth_date,
            "EMAIL":       [{"VALUE": email, "VALUE_TYPE": "WORK"}],
            "PHONE":       [{"VALUE": phone, "VALUE_TYPE": "MOBILE"}],
            "COMMENTS":    f"Создан автоматически при бронировании.",
        }
        if passport and any(passport.values()):
            # Паспортные данные в комментарий контакта (поля UF_ нужно сначала создать в Битрикс)
            passport_str = (
                f"Паспорт: {passport.get('series','')} {passport.get('number','')}, "
                f"выдан: {passport.get('issued_by','')}, "
                f"дата: {passport.get('issued_date','')}"
            )
            fields["COMMENTS"] = passport_str

        res = await self._call("crm.contact.add", {"fields": fields})
        cid = int(res) if res else 0
        logger.info("Bitrix: создан контакт id=%d name='%s'", cid, full_name)
        return cid

    # ── Сделка ────────────────────────────────────────────────────────────────

    async def create_deal(self, booking, req, calc) -> dict:
        """
        Создаёт сделку в Битрикс24 со всеми данными брони.

        Структура сделки:
          Название:   "Бронь: [Отель] / Номер [N] / [ФИО]"
          Контакт:    найден/создан по email или телефону
          Сумма:      итоговая сумма к оплате
          Стадия:     NEW (ожидает оплаты)
          Описание:   полные данные брони + ссылка на бронь в админке

        Также создаёт счёт (invoice) на эту сделку.
        """
        # Паспортные данные
        passport = {
            "series":      getattr(req, "passport_series", "") or "",
            "number":      getattr(req, "passport_number", "") or "",
            "issued_by":   getattr(req, "passport_issued_by", "") or "",
            "issued_date": str(req.passport_issued_date) if getattr(req, "passport_issued_date", None) else "",
        }

        # Создаём / находим контакт
        contact_id = await self.find_or_create_contact(
            full_name=req.guest_full_name,
            email=req.guest_email,
            phone=req.guest_phone,
            birth_date=str(req.guest_birth_date) if getattr(req, "guest_birth_date", None) else "",
            passport=passport,
        )

        # Ссылка на бронь в нашей админке
        admin_booking_url = (
            f"{settings.SITE_URL}/admin"
            f"#booking-{booking.id}"
        )

        # Названия отеля и номера (обогащаются в bookings.py перед вызовом)
        hotel_name = getattr(req, "_hotel_name", None) or str(req.hotel_id)
        room_name  = getattr(req, "_room_name",  None) or str(req.room_id)

        # Список услуг
        services_lines = "\n".join(
            f"  • {item.name} × {item.quantity}  —  {item.amount:,.0f} ₽"
            for item in calc.services_breakdown
        ) or "  —"

        # Подробное описание сделки
        nights = calc.nights
        description = (
            f"═══ ДАННЫЕ БРОНИ ═══\n"
            f"ID брони:       {booking.id}\n"
            f"Ссылка:         {admin_booking_url}\n"
            f"\n"
            f"═══ ПРОЖИВАНИЕ ═══\n"
            f"Отель:          {hotel_name}\n"
            f"Номер:          {room_name}\n"
            f"Дата заезда:    {req.check_in}\n"
            f"Дата выезда:    {req.check_out}\n"
            f"Ночей:          {nights}\n"
            f"Взрослых:       {req.adults}\n"
            f"Детей:          {req.children}\n"
            f"\n"
            f"═══ СТОИМОСТЬ ═══\n"
            f"Проживание:     {calc.room_total:,.0f} ₽  ({calc.room_price_per_night:,.0f} ₽ × {nights} ночей)\n"
            f"Услуги:\n{services_lines}\n"
            f"ИТОГО к оплате: {calc.total_amount:,.0f} ₽\n"
            f"\n"
            f"═══ ГОСТЬ ═══\n"
            f"ФИО:            {req.guest_full_name}\n"
            f"Телефон:        {req.guest_phone}\n"
            f"Email:          {req.guest_email}\n"
            f"Дата рожд.:     {getattr(req, 'guest_birth_date', '—')}\n"
        )
        if req.comment:
            description += f"\nКомментарий:    {req.comment}\n"

        if any(passport.values()):
            description += (
                f"\n═══ ПАСПОРТ ═══\n"
                f"Серия/Номер:    {passport['series']} {passport['number']}\n"
                f"Кем выдан:      {passport['issued_by']}\n"
                f"Дата выдачи:    {passport['issued_date']}\n"
            )

        # Создаём сделку
        deal_fields = {
            "TITLE": (
                f"Бронь: {hotel_name} / "
                f"{room_name} / "
                f"{req.check_in} — {req.check_out} / "
                f"{req.guest_full_name}"
            ),
            "CONTACT_ID":  contact_id,
            "STAGE_ID":    "NEW",
            "OPPORTUNITY": calc.total_amount,
            "CURRENCY_ID": "RUB",
            "COMMENTS":    description,
            # UTM-метки / дополнительные поля
            "SOURCE_ID":   "WEB",
        }

        deal_result = await self._call("crm.deal.add", {"fields": deal_fields})
        deal_id = int(deal_result) if deal_result else 0

        deal_url = (
            f"https://{self.domain}/crm/deal/details/{deal_id}/"
            if deal_id else ""
        )

        logger.info(
            "Bitrix: сделка создана deal_id=%d contact_id=%d сумма=%.0f",
            deal_id, contact_id, calc.total_amount,
        )

        # crm.invoice.add устарел в Bitrix24 — не используем

        return {
            "deal_id":    deal_id,
            "deal_url":   deal_url,
            "contact_id": contact_id,
        }

    # ── Смена стадии ─────────────────────────────────────────────────────────

    async def update_deal_stage(self, deal_id: int, stage_id: str, comment: str = "") -> bool:
        if not deal_id:
            return False
        try:
            fields: dict = {"STAGE_ID": stage_id}
            if comment:
                fields["COMMENTS"] = comment
            await self._call("crm.deal.update", {"id": deal_id, "fields": fields})
            logger.info("Bitrix: сделка %d → стадия %s", deal_id, stage_id)
            return True
        except Exception as e:
            logger.error("Bitrix update_deal_stage %d → %s: %s", deal_id, stage_id, e)
            return False

    async def cancel_deal(self, deal_id: Optional[int], reason: str = "") -> None:
        """Переводит сделку в LOSE."""
        if deal_id:
            await self.update_deal_stage(deal_id, "LOSE", reason)

    async def delete_deal(self, deal_id: Optional[int]) -> bool:
        """Удаляет сделку в Битрикс24 полностью."""
        if not deal_id:
            return False
        try:
            await self._call("crm.deal.delete", {"id": deal_id})
            logger.info("Bitrix: сделка %d удалена", deal_id)
            return True
        except Exception as e:
            logger.warning("Bitrix: не удалось удалить сделку %d: %s", deal_id, e)
            return False

    # ── Получение текущей стадии ──────────────────────────────────────────────

    async def get_deal_stage(self, deal_id: int) -> Optional[str]:
        if not deal_id:
            return None
        try:
            res = await self._call("crm.deal.get", {
                "id": deal_id,
                "select": ["ID", "STAGE_ID"],
            })
            return res.get("STAGE_ID")
        except Exception as e:
            logger.error("Bitrix get_deal_stage %d: %s", deal_id, e)
            return None

    # ── Polling: синхронизация статуса ───────────────────────────────────────

    async def sync_deal_status(self, db, booking) -> Optional[str]:
        """
        Запрашивает Битрикс о текущей стадии и обновляет статус брони.
        Fallback на случай если webhook не пришёл.
        """
        from sqlalchemy import select
        from bookings.models import StatusMapping, BookingStatus, BookingStatusHistory
        from stock import stock as stock_svc
        from datetime import datetime

        if not booking.bitrix_deal_id:
            return None

        stage_id = await self.get_deal_stage(booking.bitrix_deal_id)
        if not stage_id:
            return None

        res = await db.execute(
            select(StatusMapping).where(StatusMapping.bitrix_stage_id == stage_id)
        )
        mapping = res.scalar_one_or_none()
        if not mapping:
            return None

        new_status = mapping.internal_status
        if booking.status == new_status:
            return None

        old_status = booking.status
        booking.status = new_status
        booking.updated_at = datetime.utcnow()
        db.add(BookingStatusHistory(
            booking_id=booking.id,
            old_status=old_status,
            new_status=new_status,
            comment=f"Синхронизация с Bitrix: стадия {stage_id}",
        ))

        if new_status == BookingStatus.PAID:
            booking.expires_at = None
        if new_status in (BookingStatus.CANCELLED, BookingStatus.CANCELLED_TIMEOUT):
            await stock_svc.release_dates(db, booking.room_id, booking.check_in, booking.check_out)

        await db.commit()
        logger.info("sync_deal_status: бронь %s %s → %s", booking.id, old_status, new_status)
        return new_status
