import hashlib
import hmac
import json

from fastapi import APIRouter, Header, HTTPException, Request, status

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/webhook")


def _verify_telnyx_signature(payload: bytes, signature: str, settings) -> bool:
    if not settings.telnyx_webhook_secret:
        return True  # Skip verification in dev if no secret configured
    expected = hmac.new(
        settings.telnyx_webhook_secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/telnyx")
async def telnyx_webhook(
    request: Request,
    telnyx_signature_ed25519: str = Header(default=""),
) -> dict:
    settings = get_settings()
    body = await request.body()

    if settings.is_production and telnyx_signature_ed25519:
        if not _verify_telnyx_signature(body, telnyx_signature_ed25519, settings):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    try:
        event = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")

    event_type = event.get("data", {}).get("event_type", "unknown")
    logger.info("telnyx_webhook", event_type=event_type)

    return {"status": "ok"}


@router.get("/health")
async def health() -> dict:
    return {"status": "healthy"}
