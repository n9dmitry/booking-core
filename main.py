"""
Hotel Booking Core — точка входа.

Запуск:  uvicorn main:app --reload --port 8000
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from config import settings
from database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting Hotel Booking Core...")
    os.makedirs("data/uploads", exist_ok=True)
    await init_db()
    await _seed_defaults()

    from bookings.bookings import run_timeout_sweep
    sweep_task = asyncio.create_task(run_timeout_sweep())

    logger.info(
        "✅ Ready.\n"
        f"   Admin  → http://localhost:8000/admin\n"
        f"   Docs   → http://localhost:8000/docs\n"
        f"   ExtAPI → http://localhost:8000/ext"
    )
    yield

    sweep_task.cancel()
    try:
        await sweep_task
    except asyncio.CancelledError:
        pass
    logger.info("Stopped.")


async def _seed_defaults():
    from database import AsyncSessionLocal
    from sqlalchemy import select
    from bookings.models import StatusMapping
    from admin.models import AdminUser
    from admin.auth import hash_password

    async with AsyncSessionLocal() as db:
        defaults = [
            ("waiting_payment",   "NEW",  "Ожидает оплаты"),
            ("paid",              "WON",  "Оплачено"),
            ("cancelled",         "LOSE", "Отменено"),
            ("cancelled_timeout", "LOSE", "Таймаут оплаты"),
        ]
        for internal, stage, desc in defaults:
            r = await db.execute(
                select(StatusMapping).where(StatusMapping.internal_status == internal)
            )
            if not r.scalar_one_or_none():
                db.add(StatusMapping(internal_status=internal, bitrix_stage_id=stage, description=desc))

        r = await db.execute(select(AdminUser).where(AdminUser.email == settings.ADMIN_EMAIL))
        if not r.scalar_one_or_none():
            db.add(AdminUser(
                email=settings.ADMIN_EMAIL,
                hashed_password=hash_password(settings.ADMIN_PASSWORD),
                role="superuser",
                is_active=True,
            ))
            logger.info(f"Admin user created: {settings.ADMIN_EMAIL}")

        await db.commit()


# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Hotel Booking Core API",
    description=(
        "Централизованная система бронирования для сети отелей.\n\n"
        "**Внешний API** (`/ext/*`) используется сайтами отелей. "
        "Аутентификация: `Authorization: Bearer <token>` — токен генерируется в админке."
    ),
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    session_cookie="admin_session",
    max_age=60 * 60 * 8,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount(
    "/static",
    StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")),
    name="static",
)

app.mount(
    "/admin/static",
    StaticFiles(directory=os.path.join(os.path.dirname(__file__), "admin", "static")),
    name="admin_static",
)

# ─── Routers ──────────────────────────────────────────────────────────────────

from hotels.routes        import router as hotels_router
from bookings.routes      import router as bookings_router
from stock.routes         import router as stock_router
from admin.routes         import router as admin_router
from external_api.routes  import router as ext_router

app.include_router(hotels_router,   prefix="/api/v1")
app.include_router(bookings_router, prefix="/api/v1")
app.include_router(stock_router,    prefix="/api/v1")
app.include_router(admin_router)          # /admin
app.include_router(ext_router)            # /ext

# ─── Error handlers ───────────────────────────────────────────────────────────

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={"status": "error", "data": None, "message": str(exc)},
    )

@app.exception_handler(Exception)
async def generic_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled: {exc}")
    return JSONResponse(
        status_code=500,
        content={"status": "error", "data": None, "message": "Внутренняя ошибка сервера"},
    )

@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/admin")


@app.get("/health", tags=["System"])
async def health():
    return {"status": "ok", "service": "hotel-booking-core", "version": "2.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
