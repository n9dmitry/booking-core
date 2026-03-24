"""
Аутентификация внешнего API по Bearer-токену.
"""
from datetime import datetime
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from external_api.models import HotelApiToken

bearer_scheme = HTTPBearer(auto_error=True)


async def get_token_record(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> HotelApiToken:
    token_str = credentials.credentials
    result = await db.execute(
        select(HotelApiToken).where(
            HotelApiToken.token == token_str,
            HotelApiToken.is_active == True,
        )
    )
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(
            status_code=401,
            detail="Недействительный или неактивный API-токен",
            headers={"WWW-Authenticate": "Bearer"},
        )

    record.last_used_at = datetime.utcnow()
    await db.commit()
    return record
