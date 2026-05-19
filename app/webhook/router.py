import hashlib
import hmac
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Request, status
from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import CallSession
from app.db.session import get_session_factory

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

    data = event.get("data", {})
    event_type = data.get("event_type", "unknown")
    payload = data.get("payload", {})

    logger.info("telnyx_webhook", event_type=event_type)

    if event_type == "call.initiated":
        await _handle_call_initiated(payload)
    elif event_type == "call.answered":
        await _handle_call_answered(payload)
    elif event_type == "call.hangup":
        await _handle_call_hangup(payload)

    return {"status": "ok"}


async def _handle_call_initiated(payload: dict) -> None:
    caller = payload.get("from", "unknown")
    direction = payload.get("direction", "unknown")
    call_control_id = payload.get("call_control_id", "")
    logger.info("call_initiated", caller=caller, direction=direction, call_control_id=call_control_id)


async def _handle_call_answered(payload: dict) -> None:
    caller = payload.get("from", "unknown")
    call_control_id = payload.get("call_control_id", "")
    logger.info("call_answered", caller=caller, call_control_id=call_control_id)


async def _handle_call_hangup(payload: dict) -> None:
    """
    Safety net: if the LiveKit worker crashed before persisting the session end,
    close any open CallSession for this caller using Telnyx's reported duration.
    """
    caller = payload.get("from", "unknown")
    hangup_cause = payload.get("hangup_cause", "unknown")
    hangup_source = payload.get("hangup_source", "unknown")
    duration_ms = payload.get("call_duration_ms") or 0
    duration_seconds = int(duration_ms / 1000)

    logger.info(
        "call_hangup",
        caller=caller,
        cause=hangup_cause,
        source=hangup_source,
        duration_seconds=duration_seconds,
    )

    try:
        factory = get_session_factory()
        async with factory() as db:
            result = await db.execute(
                select(CallSession)
                .where(CallSession.caller_number == caller)
                .where(CallSession.ended_at.is_(None))
                .order_by(CallSession.started_at.desc())
                .limit(1)
            )
            session = result.scalar_one_or_none()
            if session:
                session.ended_at = datetime.now(timezone.utc)
                session.duration_seconds = duration_seconds
                await db.commit()
                logger.info("session_closed_via_webhook", session_id=session.id, caller=caller)
    except Exception as exc:
        logger.error("hangup_cleanup_error", error=str(exc), caller=caller)


@router.get("/health")
async def health() -> dict:
    return {"status": "healthy"}
