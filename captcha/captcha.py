from __future__ import annotations

import base64
import io
import random
import string
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Avoid local module/package name collision with external `captcha` library.
_THIS_DIR = Path(__file__).resolve().parent
sys.path = [p for p in sys.path if Path(p or ".").resolve() != _THIS_DIR]
from captcha.image import ImageCaptcha
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel


app = FastAPI(title="Local Captcha Test")

CAPTCHA_TTL_MINUTES = 5
CAPTCHA_LENGTH = 5
ALPHABET = string.ascii_uppercase + string.digits

# In-memory challenge store for local testing.
_challenges: dict[str, tuple[str, datetime]] = {}


class VerifyRequest(BaseModel):
    challenge_id: str
    value: str


def _cleanup_expired() -> None:
    now = datetime.now(timezone.utc)
    expired_ids = [cid for cid, (_, exp) in _challenges.items() if exp <= now]
    for cid in expired_ids:
        _challenges.pop(cid, None)


def _generate_code(length: int = CAPTCHA_LENGTH) -> str:
    return "".join(random.choice(ALPHABET) for _ in range(length))


@app.get("/")
def get_test_page() -> FileResponse:
    html_path = Path(__file__).with_name("test-captcha.html")
    return FileResponse(html_path)


@app.get("/captcha/new")
def new_captcha() -> dict[str, str]:
    _cleanup_expired()

    challenge_id = str(uuid.uuid4())
    code = _generate_code()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=CAPTCHA_TTL_MINUTES)
    _challenges[challenge_id] = (code, expires_at)

    image = ImageCaptcha(width=220, height=90)
    image_bytes = io.BytesIO()
    image.write(code, image_bytes)
    image_bytes.seek(0)
    image_base64 = base64.b64encode(image_bytes.read()).decode("ascii")

    return {
        "challenge_id": challenge_id,
        "image_base64": image_base64,
    }


@app.post("/captcha/verify")
def verify_captcha(payload: VerifyRequest) -> dict[str, str]:
    _cleanup_expired()
    stored = _challenges.get(payload.challenge_id)
    if not stored:
        raise HTTPException(status_code=404, detail="challenge_not_found_or_expired")

    expected, _ = stored
    submitted = payload.value.strip().upper()
    if submitted == expected:
        _challenges.pop(payload.challenge_id, None)
        return {"status": "success"}

    return {"status": "error"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001, reload=False)
