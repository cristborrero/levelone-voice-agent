"""
Telnyx webhook handler.

Signature verification: Ed25519 (not HMAC).
Telnyx signs with their private key; we verify with the public key from the portal.
Set TELNYX_WEBHOOK_PUBLIC_KEY in .env (Telnyx portal → Webhooks → show public key).

Event lifecycle:
  call.initiated  → create CallSession(status=ringing) in DB
  call.answered   → update status=active
  call.hangup     → safety net: close any open session if worker crashed
"""
import base64
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


# ---------------------------------------------------------------------------
# Signature verification — Ed25519
# ---------------------------------------------------------------------------

def _verify_telnyx_signature(
    payload: bytes,
    timestamp: str,
    signature_b64: str,
    public_key_b64: str,
) -> bool:
    """
    Telnyx signs: timestamp + "|" + body  with Ed25519.
    Public key is base64-encoded and available in the Telnyx portal.
    """
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        from cryptography.exceptions import InvalidSignature

        pub_key_bytes = base64.b64decode(public_key_b64)
        public_key = Ed25519PublicKey.from_public_bytes(pub_key_bytes)

        signed_payload = (timestamp + "|").encode() + payload
        sig_bytes = base64.b64decode(signature_b64)

        public_key.verify(sig_bytes, signed_payload)
        return True
    except InvalidSignature:
        return False
    except Exception as exc:
        logger.warning("signature_verification_error", error=str(exc))
        return False


# ---------------------------------------------------------------------------
# Main endpoint
# ---------------------------------------------------------------------------

@router.post("/telnyx")
async def telnyx_webhook(
    request: Request,
    telnyx_signature_ed25519: str = Header(default=""),
    telnyx_timestamp: str = Header(default=""),
) -> dict:
    settings = get_settings()
    body = await request.body()

    if settings.is_production and settings.telnyx_webhook_public_key:
        if not telnyx_signature_ed25519 or not telnyx_timestamp:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing Telnyx signature headers",
            )
        if not _verify_telnyx_signature(
            body,
            telnyx_timestamp,
            telnyx_signature_ed25519,
            settings.telnyx_webhook_public_key,
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Telnyx signature",
            )

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


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def _handle_call_initiated(payload: dict) -> None:
    """
    Pre-create a CallSession as soon as Telnyx notifies us of an inbound call.
    This gives us a DB record even before the LiveKit worker connects.

    The session ID is the call_control_id (stable across the whole call lifecycle).
    The LiveKit worker will update livekit_room and status when it takes over.
    """
    call_control_id = payload.get("call_control_id", "")
    caller = payload.get("from", "unknown")
    direction = payload.get("direction", "unknown")

    logger.info("call_initiated", caller=caller, direction=direction, call_control_id=call_control_id)

    if not call_control_id or direction != "incoming":
        # Outbound calls are initiated by us — worker handles those directly
        return

    try:
        factory = get_session_factory()
        async with factory() as db:
            # Idempotent: skip if worker already created the session
            existing = await db.get(CallSession, call_control_id)
            if existing is None:
                db.add(CallSession(
                    id=call_control_id,
                    caller_number=caller,
                    livekit_room="",  # filled by worker when room is assigned
                    status="ringing",
                ))
                await db.commit()
                logger.info("session_created_ringing", call_control_id=call_control_id, caller=caller)
    except Exception as exc:
        logger.error("call_initiated_db_error", error=str(exc), caller=caller)


async def _handle_call_answered(payload: dict) -> None:
    """
    Update CallSession status to 'active' once the call is answered.
    LiveKit will have dispatched the worker by this point.
    """
    call_control_id = payload.get("call_control_id", "")
    caller = payload.get("from", "unknown")

    logger.info("call_answered", caller=caller, call_control_id=call_control_id)

    if not call_control_id:
        return

    try:
        factory = get_session_factory()
        async with factory() as db:
            session = await db.get(CallSession, call_control_id)
            if session and session.status == "ringing":
                session.status = "active"
                await db.commit()
                logger.info("session_active", call_control_id=call_control_id)
    except Exception as exc:
        logger.error("call_answered_db_error", error=str(exc), caller=caller)


async def _handle_call_hangup(payload: dict) -> None:
    """
    Safety net: if the LiveKit worker crashed before persisting the session end,
    close any open CallSession for this caller using Telnyx's reported duration.

    Matches by caller_number (not call_control_id) because the worker may have
    created its own session ID before we had the call_control_id mapping.
    """
    caller = payload.get("from", "unknown")
    call_control_id = payload.get("call_control_id", "")
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
            # Try by call_control_id first (most precise match)
            session = None
            if call_control_id:
                session = await db.get(CallSession, call_control_id)
                if session and session.ended_at is not None:
                    session = None  # already closed by worker

            # Fallback: find open session by caller number
            if session is None:
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
                session.status = "ended"
                await db.commit()
                logger.info("session_closed_via_webhook", session_id=session.id, caller=caller)
    except Exception as exc:
        logger.error("hangup_cleanup_error", error=str(exc), caller=caller)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@router.get("/health")
async def health() -> dict:
    return {"status": "healthy"}
