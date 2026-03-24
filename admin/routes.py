from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import os
import uuid
from datetime import datetime, date, timedelta

from database import get_db
from admin import admin as svc
from admin.auth import authenticate, require_admin, require_permission, session_has_permission, hash_password
from admin.models import AdminUser, AdminRole, ROLE_LABELS, ROLE_PERMISSIONS

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

INTERNAL_STATUSES = ["waiting_payment", "paid", "cancelled", "cancelled_timeout", "checked_in", "checked_out"]
STATUS_LABELS = {
    "waiting_payment": "⏳ Ожидает оплаты",
    "paid": "✅ Оплачено",
    "cancelled": "✗ Отменено",
    "cancelled_timeout": "⌛ Таймаут",
    "checked_in": "🏨 Заехал",
    "checked_out": "🚪 Выехал",
}


def _redirect(path: str):
    return RedirectResponse(path, status_code=302)


def _check_auth(request: Request):
    return require_admin(request)


def _ctx(request: Request, **kwargs) -> dict:
    """Базовый контекст — добавляет флаги прав для шаблонов."""
    return {
        "request": request,
        "can_manage_users":  session_has_permission(request, "manage_users"),
        "can_manage_tokens": session_has_permission(request, "manage_tokens"),
        "can_manage_hotels": session_has_permission(request, "manage_hotels"),
        "can_manage_bookings": session_has_permission(request, "manage_bookings"),
        **kwargs,
    }


# ─── Auth ─────────────────────────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if request.session.get("admin_logged_in"):
        return _redirect("/admin")
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login")
async def login_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    user = await authenticate(db, email, password)
    if user:
        request.session["admin_logged_in"] = True
        request.session["admin_email"] = email
        request.session["admin_role"] = user.role
        request.session["admin_user_id"] = user.id
        return _redirect("/admin")
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": "Неверный email или пароль"},
        status_code=401,
    )


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return _redirect("/admin/login")


# ─── Dashboard ────────────────────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    redir = _check_auth(request)
    if redir:
        return redir

    hotels = await svc.list_hotels(db)
    all_bookings = await svc.list_bookings(db, limit=9999)
    recent_bookings = await svc.list_bookings(db, limit=10)

    return templates.TemplateResponse("dashboard.html", _ctx(request,
        hotels=hotels,
        hotels_count=len(hotels),
        bookings_count=len(all_bookings),
        paid_count=sum(1 for b in all_bookings if b.status == "paid"),
        pending_count=sum(1 for b in all_bookings if b.status == "waiting_payment"),
        recent_bookings=recent_bookings,
        status_labels=STATUS_LABELS,
    ))


# ─── Hotels ───────────────────────────────────────────────────────────────────

@router.get("/hotels", response_class=HTMLResponse)
async def hotels_list(request: Request, db: AsyncSession = Depends(get_db)):
    redir = _check_auth(request)
    if redir:
        return redir

    hotels = await svc.list_hotels(db)
    all_rooms = await svc.list_rooms(db)
    rooms_by_hotel = {}
    for r in all_rooms:
        rooms_by_hotel[r.hotel_id] = rooms_by_hotel.get(r.hotel_id, 0) + 1

    return templates.TemplateResponse("hotels/list.html", _ctx(request,
        hotels=hotels, rooms_by_hotel=rooms_by_hotel,
    ))


@router.get("/hotels/create", response_class=HTMLResponse)
async def hotel_create_page(request: Request):
    redir = _check_auth(request)
    if redir:
        return redir
    require_permission(request, "manage_hotels")
    return templates.TemplateResponse("hotels/create.html", _ctx(request, error=None))


@router.post("/hotels/create")
async def hotel_create(
    request: Request,
    id: str = Form(...), name: str = Form(...), address: str = Form(...),
    phone: str = Form(""), email: str = Form(""),
    check_in_time: str = Form("14:00"), check_out_time: str = Form("12:00"),
    description: str = Form(""), rules_html: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    redir = _check_auth(request)
    if redir:
        return redir
    require_permission(request, "manage_hotels")
    try:
        await svc.save_hotel(db, dict(
            id=id, name=name, address=address,
            phone=phone or None, email=email or None,
            check_in_time=check_in_time, check_out_time=check_out_time,
            description=description or None, rules_html=rules_html or None,
            is_active=True,
        ))
        return _redirect("/admin/hotels")
    except Exception as e:
        return templates.TemplateResponse("hotels/create.html", _ctx(request, error=str(e)), status_code=400)


@router.get("/hotels/{hotel_id}/edit", response_class=HTMLResponse)
async def hotel_edit_page(hotel_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    redir = _check_auth(request)
    if redir:
        return redir
    hotel = await svc.get_hotel(db, hotel_id)
    if not hotel:
        raise HTTPException(404, "Отель не найден")
    rooms = await svc.list_rooms(db, hotel_id=hotel_id)
    return templates.TemplateResponse("hotels/edit.html", _ctx(request, hotel=hotel, rooms=rooms, error=None))


@router.post("/hotels/{hotel_id}/edit")
async def hotel_edit(
    hotel_id: str, request: Request,
    name: str = Form(...), address: str = Form(...),
    phone: str = Form(""), email_field: str = Form(""),
    check_in_time: str = Form("14:00"), check_out_time: str = Form("12:00"),
    description: str = Form(""), rules_html: str = Form(""),
    is_active: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    redir = _check_auth(request)
    if redir:
        return redir
    require_permission(request, "manage_hotels")
    await svc.save_hotel(db, dict(
        id=hotel_id, name=name, address=address,
        phone=phone or None, email=email_field or None,
        check_in_time=check_in_time, check_out_time=check_out_time,
        description=description or None, rules_html=rules_html or None,
        is_active=is_active == "on",
    ))
    return _redirect("/admin/hotels")


@router.post("/hotels/{hotel_id}/delete")
async def hotel_delete(hotel_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    redir = _check_auth(request)
    if redir:
        return redir
    require_permission(request, "manage_hotels")
    await svc.delete_hotel(db, hotel_id)
    return _redirect("/admin/hotels")


# ─── Rooms ────────────────────────────────────────────────────────────────────

@router.get("/rooms", response_class=HTMLResponse)
async def rooms_list(request: Request, hotel_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    redir = _check_auth(request)
    if redir:
        return redir
    hotels = await svc.list_hotels(db)
    rooms = await svc.list_rooms(db, hotel_id=hotel_id)
    rules = await svc.list_rules(db)
    return templates.TemplateResponse("rooms/list.html", _ctx(request,
        hotels=hotels, rooms=rooms, rules=rules, selected_hotel=hotel_id or "",
    ))


@router.get("/hotels/{hotel_id}/rooms/add", response_class=HTMLResponse)
async def room_add_page(hotel_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    redir = _check_auth(request)
    if redir:
        return redir
    require_permission(request, "manage_hotels")
    hotels = await svc.list_hotels(db)
    all_rules = await svc.list_rules(db)
    return templates.TemplateResponse("rooms/edit.html", _ctx(request,
        room=None, hotels=hotels, all_rules=all_rules, default_hotel_id=hotel_id, error=None,
    ))


@router.post("/rooms/create")
async def room_create(
    request: Request,
    hotel_id: str = Form(...), number: str = Form(...), name: str = Form(...),
    base_price: float = Form(...), area_sqm: Optional[str] = Form(None),
    floor: Optional[str] = Form(None), capacity_adults: int = Form(2),
    capacity_children: int = Form(0), description: str = Form(""),
    is_active: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    redir = _check_auth(request)
    if redir:
        return redir
    require_permission(request, "manage_hotels")
    await svc.save_room(db, dict(
        hotel_id=hotel_id, number=number, name=name,
        description=description or None,
        capacity_adults=capacity_adults, capacity_children=capacity_children,
        base_price=base_price,
        area_sqm=float(area_sqm) if area_sqm else None,
        floor=int(floor) if floor else None,
        is_active=is_active == "on",
    ))
    return _redirect("/admin/rooms")


@router.get("/rooms/{room_id}/edit", response_class=HTMLResponse)
async def room_edit_page(room_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    redir = _check_auth(request)
    if redir:
        return redir
    room = await svc.get_room(db, room_id)
    if not room:
        raise HTTPException(404, "Номер не найден")
    hotels = await svc.list_hotels(db)
    all_rules = await svc.list_rules(db)
    return templates.TemplateResponse("rooms/edit.html", _ctx(request,
        room=room, hotels=hotels, all_rules=all_rules, default_hotel_id=None, error=None,
    ))


@router.post("/rooms/{room_id}/edit")
async def room_edit(
    room_id: int, request: Request,
    hotel_id: str = Form(...), number: str = Form(...), name: str = Form(...),
    base_price: float = Form(...), area_sqm: Optional[str] = Form(None),
    floor: Optional[str] = Form(None), capacity_adults: int = Form(2),
    capacity_children: int = Form(0), description: str = Form(""),
    is_active: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    redir = _check_auth(request)
    if redir:
        return redir
    require_permission(request, "manage_hotels")
    await svc.save_room(db, dict(
        id=room_id, hotel_id=hotel_id, number=number, name=name,
        description=description or None,
        capacity_adults=capacity_adults, capacity_children=capacity_children,
        base_price=base_price,
        area_sqm=float(area_sqm) if area_sqm else None,
        floor=int(floor) if floor else None,
        is_active=is_active == "on",
    ))
    return _redirect("/admin/rooms")


@router.post("/rooms/{room_id}/delete")
async def room_delete(room_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    redir = _check_auth(request)
    if redir:
        return redir
    require_permission(request, "manage_hotels")
    await svc.delete_room(db, room_id)
    return _redirect("/admin/rooms")


# ─── Bookings ─────────────────────────────────────────────────────────────────

@router.get("/bookings", response_class=HTMLResponse)
async def bookings_list(
    request: Request,
    status: Optional[str] = None, hotel_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    redir = _check_auth(request)
    if redir:
        return redir
    hotels = await svc.list_hotels(db)
    bookings = await svc.list_bookings(db, status=status, hotel_id=hotel_id)
    return templates.TemplateResponse("bookings/list.html", _ctx(request,
        bookings=bookings, hotels=hotels,
        selected_status=status or "", selected_hotel=hotel_id or "",
        pending_count=sum(1 for b in bookings if b.status == "waiting_payment"),
        status_labels=STATUS_LABELS,
    ))


@router.get("/bookings/create", response_class=HTMLResponse)
async def booking_create_page(request: Request, db: AsyncSession = Depends(get_db)):
    redir = _check_auth(request)
    if redir:
        return redir
    require_permission(request, "manage_bookings")
    hotels = await svc.list_hotels(db)
    rooms = [r for r in await svc.list_rooms(db) if r.is_active]
    return templates.TemplateResponse("bookings/create.html", _ctx(request,
        hotels=hotels, rooms=rooms, error=None,
    ))


@router.post("/bookings/create")
async def booking_create(
    request: Request,
    hotel_id: str = Form(...), room_id: int = Form(...),
    check_in: str = Form(...), check_out: str = Form(...),
    adults: int = Form(1), children: int = Form(0),
    guest_full_name: str = Form(...), guest_birth_date: str = Form(""),
    guest_phone: str = Form(...), guest_email: str = Form(...),
    comment: str = Form(""),
    passport_series: str = Form(""), passport_number: str = Form(""),
    passport_issued_by: str = Form(""), passport_issued_date: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    redir = _check_auth(request)
    if redir:
        return redir
    require_permission(request, "manage_bookings")

    from bookings.models import Booking, BookingStatus, BookingStatusHistory
    from stock import stock as stock_svc
    from bitrix.bitrix import BitrixClient
    from config import settings
    from utils import nights_count

    hotels = await svc.list_hotels(db)
    rooms_all = [r for r in await svc.list_rooms(db) if r.is_active]

    try:
        room = await svc.get_room(db, room_id)
        if not room:
            raise ValueError("Номер не найден")
        ci = date.fromisoformat(check_in)
        co = date.fromisoformat(check_out)
        if co <= ci:
            raise ValueError("Дата выезда должна быть позже даты заезда")
        if not await stock_svc.is_available(db, room.id, ci, co):
            raise ValueError("Номер недоступен на выбранные даты")

        nights = nights_count(ci, co)
        room_total = room.base_price * nights
        booking_id = str(uuid.uuid4())
        expires_at = datetime.utcnow() + timedelta(minutes=settings.BOOKING_TIMEOUT_MINUTES)

        booking = Booking(
            id=booking_id, hotel_id=hotel_id, room_id=room.id,
            check_in=ci, check_out=co, adults=adults, children=children,
            room_total=room_total, services_total=0, total_amount=room_total,
            services_json="[]", status=BookingStatus.WAITING_PAYMENT, expires_at=expires_at,
        )
        db.add(booking)
        db.add(BookingStatusHistory(booking_id=booking_id, new_status=BookingStatus.WAITING_PAYMENT, comment="Создана администратором"))
        await db.flush()
        await stock_svc.block_dates(db, room.id, ci, co, booking_id)
        await db.commit()

        try:
            bitrix = BitrixClient()
            req_obj = type("R", (), {
                "guest_full_name": guest_full_name,
                "guest_birth_date": date.fromisoformat(guest_birth_date) if guest_birth_date else None,
                "guest_phone": guest_phone, "guest_email": guest_email,
                "comment": comment or None,
                "passport_series": passport_series, "passport_number": passport_number,
                "passport_issued_by": passport_issued_by,
                "passport_issued_date": date.fromisoformat(passport_issued_date) if passport_issued_date else None,
                "check_in": booking.check_in, "check_out": booking.check_out,
                "adults": booking.adults, "children": booking.children,
                "hotel_id": booking.hotel_id, "room_id": booking.room_id, "services": [],
            })()
            from bookings.schemas import BookingCalculateResponse
            calc = BookingCalculateResponse(nights=nights, room_price_per_night=room.base_price,
                room_total=room_total, services_breakdown=[], services_total=0, total_amount=room_total)
            result = await bitrix.create_deal(booking, req_obj, calc)
            booking.bitrix_deal_id = result["deal_id"]
            booking.bitrix_deal_url = result["deal_url"]
            booking.bitrix_contact_id = result.get("contact_id")
            await db.commit()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Bitrix error: {e}")

        return _redirect(f"/admin/bookings/{booking_id}")
    except ValueError as e:
        return templates.TemplateResponse("bookings/create.html", _ctx(request,
            hotels=hotels, rooms=rooms_all, error=str(e)), status_code=400)


@router.get("/bookings/{booking_id}", response_class=HTMLResponse)
async def booking_detail(booking_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    redir = _check_auth(request)
    if redir:
        return redir
    booking = await svc.get_booking(db, booking_id)
    if not booking:
        raise HTTPException(404, "Бронь не найдена")
    from config import settings
    return templates.TemplateResponse("bookings/detail.html", _ctx(request,
        booking=booking, statuses=INTERNAL_STATUSES,
        status_labels=STATUS_LABELS, bitrix_domain=settings.BITRIX24_DOMAIN,
    ))


@router.post("/bookings/{booking_id}/status")
async def booking_change_status(
    booking_id: str, request: Request,
    new_status: str = Form(...), db: AsyncSession = Depends(get_db),
):
    redir = _check_auth(request)
    if redir:
        return redir
    require_permission(request, "manage_bookings")
    from bookings.models import Booking, BookingStatusHistory
    booking = await db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(404)
    old = booking.status
    booking.status = new_status
    booking.updated_at = datetime.utcnow()
    db.add(BookingStatusHistory(booking_id=booking_id, old_status=old, new_status=new_status, comment="Изменено администратором"))
    await db.commit()

    # Синхронизируем стадию сделки в Битрикс24
    if booking.bitrix_deal_id:
        try:
            from bitrix.bitrix import BitrixClient
            bitrix = BitrixClient()
            STAGE_MAP = {
                "paid":              "WON",
                "cancelled":         "LOSE",
                "cancelled_timeout": "LOSE",
                "waiting_payment":   "NEW",
                "checked_in":        "WON",
                "checked_out":       "WON",
            }
            stage = STAGE_MAP.get(new_status)
            if stage:
                await bitrix.update_deal_stage(booking.bitrix_deal_id, stage, f"Статус изменён администратором: {new_status}")
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Bitrix stage sync error: {e}")

    return _redirect(f"/admin/bookings/{booking_id}")


@router.post("/bookings/{booking_id}/delete")
async def booking_delete(booking_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    redir = _check_auth(request)
    if redir:
        return redir
    require_permission(request, "manage_bookings")
    from bookings.models import Booking, BookingStatusHistory
    from sqlalchemy import delete as sql_delete
    from stock import stock as stock_svc
    await db.execute(sql_delete(BookingStatusHistory).where(BookingStatusHistory.booking_id == booking_id))
    booking = await db.get(Booking, booking_id)
    if booking:
        # Удаляем сделку в Битрикс24
        try:
            from bitrix.bitrix import BitrixClient
            bitrix = BitrixClient()
            await bitrix.delete_deal(booking.bitrix_deal_id)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Bitrix delete deal error: {e}")
        try:
            await stock_svc.release_dates(db, booking.room_id, booking.check_in, booking.check_out, booking_id)
        except Exception:
            pass
        await db.delete(booking)
    await db.commit()
    return _redirect("/admin/bookings")


# ─── API Tokens ───────────────────────────────────────────────────────────────

@router.get("/api-tokens", response_class=HTMLResponse)
async def api_tokens_page(request: Request, db: AsyncSession = Depends(get_db)):
    redir = _check_auth(request)
    if redir:
        return redir
    require_permission(request, "manage_tokens")

    from external_api.models import HotelApiToken
    from config import settings as cfg

    hotels = await svc.list_hotels(db)
    result = await db.execute(select(HotelApiToken).order_by(HotelApiToken.created_at.desc()))
    tokens = result.scalars().all()

    return templates.TemplateResponse("api_tokens.html", _ctx(request,
        hotels=hotels, tokens=tokens, show_token=None, base_url=cfg.SITE_URL,
    ))


@router.post("/api-tokens/create")
async def api_token_create(
    request: Request,
    hotel_id: str = Form(...), label: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    redir = _check_auth(request)
    if redir:
        return redir
    require_permission(request, "manage_tokens")

    from external_api.models import HotelApiToken
    from config import settings as cfg

    hotel = await svc.get_hotel(db, hotel_id)
    if not hotel:
        raise HTTPException(404, "Отель не найден")

    raw_token = HotelApiToken.generate_token()
    record = HotelApiToken(hotel_id=hotel_id, token=raw_token, label=label or None, is_active=True)
    db.add(record)
    await db.commit()
    await db.refresh(record)

    hotels = await svc.list_hotels(db)
    result = await db.execute(select(HotelApiToken).order_by(HotelApiToken.created_at.desc()))
    tokens = result.scalars().all()

    return templates.TemplateResponse("api_tokens.html", _ctx(request,
        hotels=hotels, tokens=tokens,
        show_token={"id": record.id, "token": raw_token, "label": label or hotel.name},
        base_url=cfg.SITE_URL,
    ))


@router.post("/api-tokens/{token_id}/regenerate")
async def api_token_regenerate(token_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    redir = _check_auth(request)
    if redir:
        return redir
    require_permission(request, "manage_tokens")

    from external_api.models import HotelApiToken
    from config import settings as cfg

    record = await db.get(HotelApiToken, token_id)
    if not record:
        raise HTTPException(404)
    new_token = HotelApiToken.generate_token()
    record.token = new_token
    record.is_active = True
    await db.commit()

    hotels = await svc.list_hotels(db)
    result = await db.execute(select(HotelApiToken).order_by(HotelApiToken.created_at.desc()))
    tokens = result.scalars().all()

    return templates.TemplateResponse("api_tokens.html", _ctx(request,
        hotels=hotels, tokens=tokens,
        show_token={"id": record.id, "token": new_token, "label": record.label or record.hotel_id},
        base_url=cfg.SITE_URL,
    ))


@router.post("/api-tokens/{token_id}/toggle")
async def api_token_toggle(token_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    redir = _check_auth(request)
    if redir:
        return redir
    require_permission(request, "manage_tokens")
    from external_api.models import HotelApiToken
    record = await db.get(HotelApiToken, token_id)
    if record:
        record.is_active = not record.is_active
        await db.commit()
    return _redirect("/admin/api-tokens")


@router.post("/api-tokens/{token_id}/show")
async def api_token_show(token_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    redir = _check_auth(request)
    if redir:
        return redir
    require_permission(request, "manage_tokens")

    from external_api.models import HotelApiToken
    from config import settings as cfg

    record = await db.get(HotelApiToken, token_id)
    if not record:
        raise HTTPException(404)

    hotels = await svc.list_hotels(db)
    result = await db.execute(select(HotelApiToken).order_by(HotelApiToken.created_at.desc()))
    tokens = result.scalars().all()

    return templates.TemplateResponse("api_tokens.html", _ctx(request,
        hotels=hotels, tokens=tokens,
        show_token={"id": record.id, "token": record.token, "label": record.label or record.hotel_id},
        base_url=cfg.SITE_URL,
    ))


@router.post("/api-tokens/{token_id}/delete")
async def api_token_delete(token_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    redir = _check_auth(request)
    if redir:
        return redir
    require_permission(request, "manage_tokens")
    from external_api.models import HotelApiToken
    record = await db.get(HotelApiToken, token_id)
    if record:
        await db.delete(record)
        await db.commit()
    return _redirect("/admin/api-tokens")


# ─── Users (только superuser) ─────────────────────────────────────────────────

@router.get("/users", response_class=HTMLResponse)
async def users_page(request: Request, db: AsyncSession = Depends(get_db)):
    redir = _check_auth(request)
    if redir:
        return redir
    require_permission(request, "manage_users")

    result = await db.execute(select(AdminUser).order_by(AdminUser.created_at.desc()))
    users = result.scalars().all()
    current_id = request.session.get("admin_user_id")

    return templates.TemplateResponse("users.html", _ctx(request,
        users=users,
        roles=AdminRole,
        role_labels=ROLE_LABELS,
        current_user_id=current_id,
        error=None, success=None,
    ))


@router.post("/users/create")
async def user_create(
    request: Request,
    email: str = Form(...),
    full_name: str = Form(""),
    password: str = Form(...),
    role: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    redir = _check_auth(request)
    if redir:
        return redir
    require_permission(request, "manage_users")

    result = await db.execute(select(AdminUser).where(AdminUser.email == email))
    if result.scalar_one_or_none():
        users_res = await db.execute(select(AdminUser).order_by(AdminUser.created_at.desc()))
        return templates.TemplateResponse("users.html", _ctx(request,
            users=users_res.scalars().all(),
            roles=AdminRole, role_labels=ROLE_LABELS,
            current_user_id=request.session.get("admin_user_id"),
            error=f"Пользователь с email {email} уже существует",
            success=None,
        ), status_code=400)

    if role not in [r.value for r in AdminRole]:
        raise HTTPException(400, "Недопустимая роль")

    user = AdminUser(
        email=email,
        full_name=full_name or None,
        hashed_password=hash_password(password),
        role=role,
        is_active=True,
    )
    db.add(user)
    await db.commit()

    users_res = await db.execute(select(AdminUser).order_by(AdminUser.created_at.desc()))
    return templates.TemplateResponse("users.html", _ctx(request,
        users=users_res.scalars().all(),
        roles=AdminRole, role_labels=ROLE_LABELS,
        current_user_id=request.session.get("admin_user_id"),
        error=None, success=f"Пользователь {email} создан",
    ))


@router.post("/users/{user_id}/edit")
async def user_edit(
    user_id: int, request: Request,
    full_name: str = Form(""),
    role: str = Form(...),
    is_active: Optional[str] = Form(None),
    new_password: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    redir = _check_auth(request)
    if redir:
        return redir
    require_permission(request, "manage_users")

    current_id = request.session.get("admin_user_id")

    user = await db.get(AdminUser, user_id)
    if not user:
        raise HTTPException(404)

    # Нельзя понизить или деактивировать себя
    if user.id == current_id:
        if role != AdminRole.SUPERUSER:
            raise HTTPException(400, "Нельзя изменить роль своей учётной записи")
        if is_active != "on":
            raise HTTPException(400, "Нельзя деактивировать свою учётную запись")

    user.full_name = full_name or None
    user.role = role
    user.is_active = is_active == "on"
    if new_password.strip():
        user.hashed_password = hash_password(new_password.strip())

    await db.commit()
    return _redirect("/admin/users")


@router.post("/users/{user_id}/delete")
async def user_delete(user_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    redir = _check_auth(request)
    if redir:
        return redir
    require_permission(request, "manage_users")

    current_id = request.session.get("admin_user_id")
    if user_id == current_id:
        raise HTTPException(400, "Нельзя удалить свою учётную запись")

    user = await db.get(AdminUser, user_id)
    if user:
        await db.delete(user)
        await db.commit()
    return _redirect("/admin/users")
