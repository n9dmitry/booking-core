"""
Запусти в папке hotels чтобы проверить все импорты и БД:
    python diagnose_backend.py
"""
import sys
import asyncio

print(f"Python: {sys.version}")
print(f"Path: {sys.executable}\n")

errors = []

# Проверяем все импорты
modules = [
    "fastapi", "uvicorn", "sqlalchemy", "aiosqlite",
    "pydantic", "pydantic_settings", "httpx",
    "bcrypt", "jose", "cryptography", "jinja2",
    "itsdangerous", "multipart",
]

print("=== Проверка зависимостей ===")
for m in modules:
    try:
        __import__(m)
        print(f"  OK  {m}")
    except ImportError as e:
        print(f"  ERR {m}: {e}")
        errors.append(f"Missing: {m}")

print("\n=== Проверка модулей проекта ===")
project_modules = [
    "config", "database", "utils",
    "hotels.models", "bookings.models", "stock.models",
    "admin.models", "admin.auth", "admin.routes",
    "external_api.models", "external_api.auth",
    "external_api.routes", "external_api.crypto",
    "bitrix.bitrix",
]
for m in project_modules:
    try:
        __import__(m)
        print(f"  OK  {m}")
    except Exception as e:
        print(f"  ERR {m}: {e}")
        errors.append(f"{m}: {e}")

print("\n=== Проверка .env ===")
try:
    from config import settings
    print(f"  DATABASE_URL:    {settings.DATABASE_URL}")
    print(f"  ADMIN_EMAIL:     {settings.ADMIN_EMAIL}")
    print(f"  GUEST_DATA_KEY:  {'SET (' + str(len(settings.GUEST_DATA_KEY)) + ' chars)' if settings.GUEST_DATA_KEY else 'EMPTY — шифрование не работает'}")
    print(f"  BITRIX_DOMAIN:   {settings.BITRIX24_DOMAIN or 'не задан'}")
except Exception as e:
    print(f"  ERR config: {e}")
    errors.append(str(e))

print("\n=== Проверка шифрования ===")
try:
    if settings.GUEST_DATA_KEY:
        from external_api.crypto import encrypt_guest, decrypt_guest
        test = {"full_name": "Тест", "phone": "+79991234567"}
        enc = encrypt_guest(test)
        dec = decrypt_guest(enc)
        assert dec == test
        print(f"  OK  Fernet encrypt/decrypt работает")
    else:
        print(f"  WARN GUEST_DATA_KEY не задан — добавь в .env")
except Exception as e:
    print(f"  ERR crypto: {e}")
    errors.append(str(e))

print("\n=== Проверка БД ===")
async def check_db():
    try:
        from database import init_db, AsyncSessionLocal
        await init_db()
        async with AsyncSessionLocal() as db:
            from sqlalchemy import text
            result = await db.execute(text("SELECT 1"))
            print(f"  OK  БД доступна")
        return True
    except Exception as e:
        print(f"  ERR БД: {e}")
        errors.append(str(e))
        return False

asyncio.run(check_db())

print(f"\n{'='*60}")
if errors:
    print(f"❌ Найдено {len(errors)} проблем:")
    for e in errors:
        print(f"   • {e}")
else:
    print("✅ Всё OK — проблема в другом месте")
print('='*60)
