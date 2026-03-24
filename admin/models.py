import enum
from sqlalchemy import String, Integer, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from typing import Optional
from database import Base


class AdminRole(str, enum.Enum):
    SUPERUSER  = "superuser"   # всё + управление пользователями
    ADMIN      = "admin"       # всё кроме управления пользователями
    MANAGER    = "manager"     # создание/редактирование броней, номеров
    VIEWER     = "viewer"      # только просмотр


ROLE_LABELS = {
    AdminRole.SUPERUSER: "Суперпользователь",
    AdminRole.ADMIN:     "Администратор",
    AdminRole.MANAGER:   "Менеджер",
    AdminRole.VIEWER:    "Просмотр",
}

# Что может каждая роль (набор «разрешений»)
ROLE_PERMISSIONS = {
    AdminRole.SUPERUSER: {"view", "manage_bookings", "manage_hotels", "manage_tokens", "manage_users"},
    AdminRole.ADMIN:     {"view", "manage_bookings", "manage_hotels", "manage_tokens"},
    AdminRole.MANAGER:   {"view", "manage_bookings"},
    AdminRole.VIEWER:    {"view"},
}


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(30), default=AdminRole.VIEWER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def has_permission(self, perm: str) -> bool:
        return perm in ROLE_PERMISSIONS.get(self.role, set())
