from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/bookings.db"
    SECRET_KEY: str = "dev-secret-key-change-in-production"

    ADMIN_EMAIL: str = "admin@hotel.ru"
    ADMIN_PASSWORD: str = "admin123"

    BITRIX24_DOMAIN: str = ""
    BITRIX24_WEBHOOK_TOKEN: str = ""

    # Базовый URL сайта — вставляется в сделку как ссылка на бронь в админке
    SITE_URL: str = "http://localhost:8000"

    YANDEX_CAPTCHA_SECRET_KEY: str = ""

    SMTP_HOST: str = "smtp.yandex.ru"
    SMTP_PORT: int = 465
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = ""

    BOOKING_TIMEOUT_MINUTES: int = 20

    # Шифрование ПД гостей (Fernet key — одинаковый в обоих проектах)
    # Генерация: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    GUEST_DATA_KEY: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
