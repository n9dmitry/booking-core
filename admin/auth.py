"""Session-based admin authentication with role support."""
from datetime import datetime
from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from admin.models import AdminUser, AdminRole, ROLE_PERMISSIONS
import bcrypt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


async def authenticate(db: AsyncSession, email: str, password: str) -> AdminUser | None:
    result = await db.execute(
        select(AdminUser).where(AdminUser.email == email, AdminUser.is_active == True)
    )
    user = result.scalar_one_or_none()
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    # обновляем время последнего входа
    user.last_login_at = datetime.utcnow()
    await db.commit()
    return user


def require_admin(request: Request):
    """Возвращает RedirectResponse если не авторизован, иначе None."""
    if not request.session.get("admin_logged_in"):
        return RedirectResponse("/admin/login", status_code=302)
    return None


def require_permission(request: Request, perm: str):
    """
    Проверяет что у текущего пользователя есть разрешение perm.
    Бросает 403 если нет.
    """
    role = request.session.get("admin_role", "viewer")
    allowed = ROLE_PERMISSIONS.get(role, set())
    if perm not in allowed:
        raise HTTPException(
            status_code=403,
            detail=f"Недостаточно прав. Требуется: {perm}"
        )


def session_has_permission(request: Request, perm: str) -> bool:
    role = request.session.get("admin_role", "viewer")
    return perm in ROLE_PERMISSIONS.get(role, set())
