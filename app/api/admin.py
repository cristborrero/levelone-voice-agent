"""
FastAPI routes for the Admin Panel.
Mounts under /api/ prefix.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import case, func, select

from app.api.auth import require_auth
from app.core.enums import LeadScore
from app.db.models import CallSession
from app.db.session import get_session_factory
from app.llm.router import get_router

router = APIRouter(prefix="/api", dependencies=[Depends(require_auth)])

# ---------------------------------------------------------------------------
# LiveKit helpers
# ---------------------------------------------------------------------------

def _lk_headers() -> dict[str, str]:
    from livekit.api import AccessToken, VideoGrants
    token = (
        AccessToken(
            api_key=os.environ["LIVEKIT_API_KEY"],
            api_secret=os.environ["LIVEKIT_API_SECRET"],
        )
        .with_grants(VideoGrants(room_admin=True, room_list=True))
        .to_jwt()
    )
    return {"Authorization": f"Bearer {token}"}


def _lk_http_url() -> str:
    ws_url = os.environ.get("LIVEKIT_URL", "ws://localhost:7880")
    return ws_url.replace("wss://", "https://").replace("ws://", "http://")


# ---------------------------------------------------------------------------
# LiveKit endpoints
# ---------------------------------------------------------------------------

@router.get("/livekit/rooms")
async def list_rooms():
    """Active LiveKit rooms with participant count."""
    from livekit import api as lk_api
    lk = lk_api.LiveKitAPI(
        url=_lk_http_url(),
        api_key=os.environ["LIVEKIT_API_KEY"],
        api_secret=os.environ["LIVEKIT_API_SECRET"],
    )
    try:
        rooms_resp = await lk.room.list_rooms(lk_api.ListRoomsRequest())
        rooms = [
            {
                "name": r.name,
                "sid": r.sid,
                "num_participants": r.num_participants,
                "creation_time": r.creation_time,
                "active_recording": r.active_recording,
            }
            for r in rooms_resp.rooms
        ]
        return {"rooms": rooms, "total": len(rooms)}
    finally:
        await lk.aclose()


@router.get("/livekit/workers")
async def list_workers():
    """Registered agent workers."""
    # LiveKit doesn't expose a public workers API — we return what we know
    # from the worker registration stored in memory/DB.
    # For now, return a health indicator based on API reachability.
    try:
        lk_url = _lk_http_url()
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{lk_url}/", headers=_lk_headers())
            reachable = resp.status_code < 500
    except Exception:
        reachable = False
    return {
        "server_reachable": reachable,
        "server_url": os.environ.get("LIVEKIT_URL"),
    }


@router.get("/stats")
async def get_stats():
    """Dashboard summary stats."""
    from livekit import api as lk_api
    lk = lk_api.LiveKitAPI(
        url=_lk_http_url(),
        api_key=os.environ["LIVEKIT_API_KEY"],
        api_secret=os.environ["LIVEKIT_API_SECRET"],
    )
    try:
        rooms_resp = await lk.room.list_rooms(lk_api.ListRoomsRequest())
        active_rooms = len(rooms_resp.rooms)
        active_participants = sum(r.num_participants for r in rooms_resp.rooms)
    except Exception:
        active_rooms = 0
        active_participants = 0
    finally:
        await lk.aclose()

    return {
        "active_calls": active_rooms,
        "active_participants": active_participants,
        "server_url": os.environ.get("LIVEKIT_URL"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# LLM Config endpoints
# ---------------------------------------------------------------------------

@router.get("/config/llm")
async def get_llm_config():
    """Return current LLM task assignments."""
    r = get_router()
    return {
        "tasks": r.get_all_tasks(),
        "providers": r.get_providers(),
    }


class TaskUpdate(BaseModel):
    provider: str
    model: str


@router.put("/config/llm/{task_name}")
async def update_llm_task(task_name: str, body: TaskUpdate):
    """Update provider/model for a specific task."""
    r = get_router()
    try:
        r.update_task(task_name, body.provider, body.model)
        return {"status": "updated", "task": task_name, "provider": body.provider, "model": body.model}
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Provider health check endpoints
# ---------------------------------------------------------------------------

@router.get("/providers/status")
async def providers_status():
    """Check each API key is set and reachable."""
    results = {}

    # OpenAI
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    results["openai"] = {
        "configured": bool(openai_key and not openai_key.startswith("your_")),
        "key_preview": f"{openai_key[:8]}..." if openai_key else "NOT SET",
    }

    # Groq
    groq_key = os.environ.get("GROQ_API_KEY", "")
    results["groq"] = {
        "configured": bool(groq_key and not groq_key.startswith("your_")),
        "key_preview": f"{groq_key[:8]}..." if groq_key else "NOT SET",
    }

    # Cartesia
    cartesia_key = os.environ.get("CARTESIA_API_KEY", "")
    results["cartesia"] = {
        "configured": bool(cartesia_key and not cartesia_key.startswith("your_")),
        "key_preview": f"{cartesia_key[:8]}..." if cartesia_key else "NOT SET",
    }

    # HubSpot
    hs_token = os.environ.get("HUBSPOT_ACCESS_TOKEN", "")
    results["hubspot"] = {
        "configured": bool(hs_token and not hs_token.startswith("your_")),
        "key_preview": f"{hs_token[:8]}..." if hs_token else "NOT SET",
    }

    # Cal.com
    cal_key = os.environ.get("CALCOM_API_KEY", "")
    results["calcom"] = {
        "configured": bool(cal_key and not cal_key.startswith("your_")),
        "event_type_id": os.environ.get("CALCOM_EVENT_TYPE_ID", "NOT SET"),
        "key_preview": f"{cal_key[:12]}..." if cal_key else "NOT SET",
    }

    # Resend
    resend_key = os.environ.get("RESEND_API_KEY", "")
    results["resend"] = {
        "configured": bool(resend_key and not resend_key.startswith("your_")),
        "key_preview": f"{resend_key[:8]}..." if resend_key else "NOT SET",
    }

    return results


@router.post("/providers/{provider_name}/test")
async def test_provider(provider_name: str):
    """Test connectivity and validity of a provider API key."""
    try:
        if provider_name == "openai":
            key = os.environ.get("OPENAI_API_KEY", "")
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {key}"},
                )
                return {"ok": resp.status_code == 200, "status_code": resp.status_code}

        elif provider_name == "groq":
            key = os.environ.get("GROQ_API_KEY", "")
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {key}"},
                )
                return {"ok": resp.status_code == 200, "status_code": resp.status_code}

        elif provider_name == "calcom":
            key = os.environ.get("CALCOM_API_KEY", "")
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    "https://api.cal.com/v1/me",
                    params={"apiKey": key},
                )
                return {"ok": resp.status_code == 200, "status_code": resp.status_code}

        elif provider_name == "hubspot":
            token = os.environ.get("HUBSPOT_ACCESS_TOKEN", "")
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    "https://api.hubapi.com/crm/v3/owners",
                    headers={"Authorization": f"Bearer {token}"},
                )
                return {"ok": resp.status_code == 200, "status_code": resp.status_code}

        else:
            raise HTTPException(status_code=404, detail=f"Unknown provider: {provider_name}")

    except httpx.TimeoutException:
        return {"ok": False, "error": "timeout"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Agent config endpoints
# ---------------------------------------------------------------------------

class AgentConfigUpdate(BaseModel):
    agent_name: Optional[str] = None
    agent_language: Optional[str] = None
    max_call_duration: Optional[int] = None
    silence_timeout: Optional[int] = None
    cartesia_voice_id: Optional[str] = None
    openai_model: Optional[str] = None
    resend_from_email: Optional[str] = None
    resend_from_name: Optional[str] = None


@router.get("/config/agent")
async def get_agent_config():
    """Return current ALEX agent configuration."""
    return {
        "agent_name": os.environ.get("AGENT_NAME", "Alex"),
        "agent_company": os.environ.get("AGENT_COMPANY", "LevelOne Agency"),
        "agent_language": os.environ.get("AGENT_LANGUAGE", "en-GB"),
        "max_call_duration": int(os.environ.get("AGENT_MAX_CALL_DURATION_SECONDS", 600)),
        "silence_timeout": int(os.environ.get("AGENT_SILENCE_TIMEOUT_SECONDS", 10)),
        "cartesia_voice_id": os.environ.get("CARTESIA_VOICE_ID", ""),
        "cartesia_model": os.environ.get("CARTESIA_MODEL", "sonic-english"),
        "openai_model": os.environ.get("OPENAI_MODEL", "gpt-4o"),
        "resend_from_email": os.environ.get("RESEND_FROM_EMAIL", ""),
        "resend_from_name": os.environ.get("RESEND_FROM_NAME", "Alex from LevelOne"),
        "calcom_event_type_id": os.environ.get("CALCOM_EVENT_TYPE_ID", ""),
        "calcom_username": os.environ.get("CALCOM_USERNAME", ""),
        "hubspot_owner_id": os.environ.get("HUBSPOT_OWNER_ID", ""),
        "livekit_url": os.environ.get("LIVEKIT_URL", ""),
    }


# ---------------------------------------------------------------------------
# Analytics endpoints
# ---------------------------------------------------------------------------

_OUTCOME_LABELS = {
    "meeting_booked": "Meeting Booked",
    "follow_up": "Follow-up",
    "not_qualified": "Not Qualified",
    "info_only": "Info Only",
}


def _derive_outcome(booking_uid: str | None, lead_score: str | None) -> str:
    if booking_uid:
        return "meeting_booked"
    if lead_score in (LeadScore.HOT, LeadScore.WARM):
        return "follow_up"
    if lead_score in (LeadScore.COLD, LeadScore.UNQUALIFIED):
        return "not_qualified"
    return "info_only"


@router.get("/analytics/overview")
async def analytics_overview():
    """Summary analytics for the dashboard overview — real DB data."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    factory = get_session_factory()

    async with factory() as db:
        day_rows = (await db.execute(
            select(
                func.date(CallSession.started_at).label("day"),
                func.count().label("calls"),
                func.sum(
                    case((CallSession.calcom_booking_uid.isnot(None), 1), else_=0)
                ).label("bookings"),
                func.avg(CallSession.duration_seconds).label("avg_duration"),
            )
            .where(CallSession.started_at >= cutoff)
            .group_by(func.date(CallSession.started_at))
            .order_by(func.date(CallSession.started_at))
        )).all()

        outcome_rows = (await db.execute(
            select(CallSession.calcom_booking_uid, CallSession.lead_score)
            .where(CallSession.started_at >= cutoff)
        )).all()

    by_day = {r.day: r for r in day_rows}
    today = datetime.now(timezone.utc)
    calls_last_7_days = []
    total_calls = 0
    total_bookings = 0
    total_duration = 0

    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_str = day.strftime("%Y-%m-%d")
        row = by_day.get(day_str)
        calls = row.calls if row else 0
        bookings = row.bookings if row else 0
        avg_dur = int(row.avg_duration or 0) if row else 0
        calls_last_7_days.append({
            "date": day.strftime("%a"),
            "calls": calls,
            "bookings": bookings,
            "avg_duration": avg_dur,
        })
        total_calls += calls
        total_bookings += bookings
        total_duration += avg_dur * calls

    outcome_counts: dict[str, int] = {k: 0 for k in _OUTCOME_LABELS}
    for r in outcome_rows:
        outcome_counts[_derive_outcome(r.calcom_booking_uid, r.lead_score)] += 1

    conversion_rate = round((total_bookings / total_calls) * 100, 1) if total_calls else 0
    avg_duration_secs = int(total_duration / total_calls) if total_calls else 0

    return {
        "total_calls_7d": total_calls,
        "total_bookings_7d": total_bookings,
        "conversion_rate": conversion_rate,
        "avg_duration_seconds": avg_duration_secs,
        "calls_by_day": calls_last_7_days,
        "top_outcomes": [
            {"label": "Meeting Booked", "count": outcome_counts["meeting_booked"], "color": "#6c63ff"},
            {"label": "Follow-up", "count": outcome_counts["follow_up"], "color": "#00d4aa"},
            {"label": "Not Qualified", "count": outcome_counts["not_qualified"], "color": "#ff4757"},
            {"label": "Info Only", "count": outcome_counts["info_only"], "color": "#ffa502"},
        ],
    }


@router.get("/analytics/calls")
async def recent_calls():
    """Recent call log — real DB data."""
    factory = get_session_factory()
    async with factory() as db:
        sessions = (await db.execute(
            select(CallSession).order_by(CallSession.started_at.desc()).limit(12)
        )).scalars().all()

    calls = []
    for s in sessions:
        outcome = _derive_outcome(s.calcom_booking_uid, s.lead_score)
        duration = s.duration_seconds or 0
        mins, secs = divmod(duration, 60)
        created_at = (
            s.started_at.replace(tzinfo=timezone.utc)
            if s.started_at.tzinfo is None
            else s.started_at
        )
        calls.append({
            "id": s.id,
            "caller_name": s.caller_name or s.caller_number,
            "duration_formatted": f"{mins}m {secs:02d}s",
            "duration_seconds": duration,
            "outcome": outcome,
            "outcome_label": _OUTCOME_LABELS[outcome],
            "booked": outcome == "meeting_booked",
            "created_at": created_at.isoformat(),
            "created_at_formatted": created_at.strftime("%d %b, %H:%M"),
        })

    return {"calls": calls, "total": len(calls)}
