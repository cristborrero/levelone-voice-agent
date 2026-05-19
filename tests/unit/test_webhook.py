"""Unit tests for Telnyx webhook handler."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

os.environ.setdefault("OPENAI_API_KEY", "test")
os.environ.setdefault("GROQ_API_KEY", "test")
os.environ.setdefault("LIVEKIT_URL", "ws://localhost:7880")
os.environ.setdefault("LIVEKIT_API_KEY", "test")
os.environ.setdefault("LIVEKIT_API_SECRET", "test")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from app.db.models import Base, CallSession  # noqa: E402
from app.main import create_app  # noqa: E402

app = create_app()
client = TestClient(app)


def _event(event_type: str, payload: dict) -> bytes:
    return json.dumps({"data": {"event_type": event_type, "payload": payload}}).encode()


@pytest.fixture(autouse=True)
async def in_memory_db(monkeypatch: pytest.MonkeyPatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr("app.db.session._session_factory", factory)
    monkeypatch.setattr("app.webhook.router.get_session_factory", lambda: factory)
    return factory


# ---------------------------------------------------------------------------
# Basic routing
# ---------------------------------------------------------------------------

def test_unknown_event_returns_ok():
    resp = client.post("/webhook/telnyx", content=_event("call.unknown", {}))
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_invalid_json_returns_400():
    resp = client.post("/webhook/telnyx", content=b"not-json")
    assert resp.status_code == 400


def test_call_initiated_returns_ok():
    payload = {
        "call_control_id": "abc123",
        "from": "+441234567890",
        "to": "+441111111111",
        "direction": "incoming",
    }
    resp = client.post("/webhook/telnyx", content=_event("call.initiated", payload))
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_call_answered_returns_ok():
    payload = {
        "call_control_id": "abc123",
        "from": "+441234567890",
    }
    resp = client.post("/webhook/telnyx", content=_event("call.answered", payload))
    assert resp.status_code == 200


def test_call_hangup_returns_ok_no_session():
    """Hangup with no matching session in DB — should not crash."""
    payload = {
        "from": "+441234567890",
        "hangup_cause": "normal_clearing",
        "hangup_source": "caller",
        "call_duration_ms": 30000,
    }
    resp = client.post("/webhook/telnyx", content=_event("call.hangup", payload))
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Hangup safety net — closes open sessions
# ---------------------------------------------------------------------------

async def test_hangup_closes_open_session(in_memory_db):
    caller = "+441234567890"
    async with in_memory_db() as db:
        db.add(CallSession(
            id="sess-001",
            caller_number=caller,
            livekit_room="room-001",
            started_at=datetime.now(timezone.utc),
        ))
        await db.commit()

    payload = {
        "from": caller,
        "hangup_cause": "normal_clearing",
        "hangup_source": "caller",
        "call_duration_ms": 45000,
    }
    resp = client.post("/webhook/telnyx", content=_event("call.hangup", payload))
    assert resp.status_code == 200

    async with in_memory_db() as db:
        session = await db.get(CallSession, "sess-001")
        assert session.ended_at is not None
        assert session.duration_seconds == 45


async def test_hangup_skips_already_closed_session(in_memory_db):
    """If session already has ended_at set, webhook should not overwrite it."""
    caller = "+441234567890"
    original_end = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    async with in_memory_db() as db:
        db.add(CallSession(
            id="sess-002",
            caller_number=caller,
            livekit_room="room-002",
            started_at=datetime.now(timezone.utc),
            ended_at=original_end,
            duration_seconds=60,
        ))
        await db.commit()

    payload = {
        "from": caller,
        "hangup_cause": "normal_clearing",
        "call_duration_ms": 99000,
    }
    resp = client.post("/webhook/telnyx", content=_event("call.hangup", payload))
    assert resp.status_code == 200

    async with in_memory_db() as db:
        session = await db.get(CallSession, "sess-002")
        assert session.duration_seconds == 60  # not overwritten


async def test_hangup_picks_most_recent_open_session(in_memory_db):
    """If multiple open sessions for the same caller, only the latest is closed."""
    caller = "+441234567890"
    async with in_memory_db() as db:
        db.add(CallSession(
            id="sess-old",
            caller_number=caller,
            livekit_room="room-old",
            started_at=datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
        ))
        db.add(CallSession(
            id="sess-new",
            caller_number=caller,
            livekit_room="room-new",
            started_at=datetime(2026, 1, 1, 11, 0, 0, tzinfo=timezone.utc),
        ))
        await db.commit()

    payload = {
        "from": caller,
        "hangup_cause": "normal_clearing",
        "call_duration_ms": 20000,
    }
    client.post("/webhook/telnyx", content=_event("call.hangup", payload))

    async with in_memory_db() as db:
        old = await db.get(CallSession, "sess-old")
        new = await db.get(CallSession, "sess-new")
        assert old.ended_at is None       # untouched
        assert new.ended_at is not None   # closed
        assert new.duration_seconds == 20
