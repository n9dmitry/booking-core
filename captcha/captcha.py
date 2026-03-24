"""Yandex SmartCaptcha token verification."""
import logging
import httpx
from config import settings

logger = logging.getLogger(__name__)

VERIFY_URL = "https://smartcaptcha.yandexcloud.net/validate"


async def verify_captcha(token: str) -> bool:
    """
    Verify Yandex SmartCaptcha token.
    Returns True if valid. In dev mode (no secret key configured) always returns True.
    """
    if not settings.YANDEX_CAPTCHA_SECRET_KEY:
        logger.debug("Captcha secret not configured — skipping verification (dev mode)")
        return True

    if not token:
        return False

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(VERIFY_URL, data={
                "secret": settings.YANDEX_CAPTCHA_SECRET_KEY,
                "token":  token,
            })
            data = resp.json()
            ok = data.get("status") == "ok"
            if not ok:
                logger.warning(f"Captcha rejected: {data}")
            return ok
    except Exception as e:
        logger.error(f"Captcha verify error: {e}")
        return False
