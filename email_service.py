"""Simple SMTP email sender (no external deps beyond stdlib)."""
import smtplib
import ssl
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from config import settings

logger = logging.getLogger(__name__)


async def send_email(to: str, subject: str, html: str):
    """Send HTML email. Silently skips if SMTP not configured."""
    if not settings.SMTP_USER:
        logger.info(f"[EMAIL SKIP] To: {to} | Subject: {subject}")
        return

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = settings.EMAIL_FROM or settings.SMTP_USER
        msg["To"]      = to
        msg.attach(MIMEText(html, "html", "utf-8"))

        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, context=ctx) as server:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)

        logger.info(f"Email sent → {to}: {subject}")
    except Exception as e:
        logger.error(f"Email send failed → {to}: {e}")
