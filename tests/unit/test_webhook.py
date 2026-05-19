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
# call.initiated — creates CallSession with status=ringing
# ---------------------------------------------------------------------------

async def test_call_initiated_creates_session(in_memory_db):
    """Inbound call.initiated creates a ringing CallSession using call_control_id as ID."""
    payload = {
        "call_control_id": "ctrl-001",
        "from": "+441234567890",
        "to": "+441111111111",
        "direction": "incoming",
    }
    resp = client.post("/webhook/telnyx", content=_event("call.initiated", payload))
    assert resp.status_code == 200

    async with in_memory_db() as db:
        session = await db.get(CallSession, "ctrl-001")
        assert session is not None
        assert session.caller_number == "+441234567890"
        assert session.status == "ringing"
        assert session.livekit_room == ""


async def test_call_initiated_outbound_skipped(in_memory_db):
    """Outbound calls should not create a session — worker handles those."""
    payload = {
        "call_control_id": "ctrl-out-001",
        "from": "+441234567890",
        "to": "+441111111111",
        "direction": "outgoing",
    }
    client.post("/webhook/telnyx", content=_event("call.initiated", payload))

    async with in_memory_db() as db:
        session = await db.get(CallSession, "ctrl-out-001")
        assert session is None


async def test_call_initiated_idempotent(in_memory_db):
    """If worker already created the session, call.initiated does not duplicate it."""
    async with in_memory_db() as db:
        db.add(CallSession(
            id="ctrl-002",
            caller_number="+441234567890",
            livekit_room="room-already-set",
            status="active",
        ))
        await db.commit()

    payload = {
        "call_control_id": "ctrl-002",
        "from": "+441234567890",
        "to": "+441111111111",
        "direction": "incoming",
    }
    client.post("/webhook/telnyx", content=_event("call.initiated", payload))

    async with in_memory_db() as db:
        session = await db.get(CallSession, "ctrl-002")
        # Should be untouched — worker's data preserved
        assert session.status == "active"
        assert session.livekit_room == "room-already-set"


async def test_call_initiated_no_call_control_id_skipped(in_memory_db):
    """Events without call_control_id should not create a broken session."""
    payload = {
        "from": "+441234567890",
        "direction": "incoming",
    }
    resp = client.post("/webhook/telnyx", content=_event("call.initiated", payload))
    assert resp.status_code == 200

    async with in_memory_db() as db:
        from sqlalchemy import select, func
        count = (await db.execute(select(func.count()).select_from(CallSession))).scalar()
        assert count == 0


# ---------------------------------------------------------------------------
# call.answered — updates status to active
# ---------------------------------------------------------------------------

async def test_call_answered_updates_status(in_memory_db):
    """call.answered transitions status from ringing to active."""
    async with in_memory_db() as db:
        db.add(CallSession(
            id="ctrl-003",
            caller_number="+441234567890",
            livekit_room="",
            status="ringing",
        ))
        await db.commit()

    payload = {
        "call_control_id": "ctrl-003",
        "from": "+441234567890",
    }
    client.post("/webhook/telnyx", content=_event("call.answered", payload))

    async with in_memory_db() as db:
        session = await db.get(CallSession, "ctrl-003")
        assert session.status == "active"


async def test_call_answered_no_session_does_not_crash(in_memory_db):
    """call.answered with unknown call_control_id should not raise."""
    payload = {
        "call_control_id": "ctrl-nonexistent",
        "from": "+441234567890",
    }
    resp = client.post("/webhook/telnyx", content=_event("call.answered", payload))
    assert resp.status_code == 200


async def test_call_answered_does_not_overwrite_active(in_memory_db):
    """If session is already active (set by worker), answered does not regress it."""
    async with in_memory_db() as db:
        db.add(CallSession(
            id="ctrl-004",
            caller_number="+441234567890",
            livekit_room="room-live",
            status="active",
        ))
        await db.commit()

    payload = {"call_control_id": "ctrl-004", "from": "+441234567890"}
    client.post("/webhook/telnyx", content=_event("call.answered", payload))

    async with in_memory_db() as db:
        session = await db.get(CallSession, "ctrl-004")
        assert session.status == "active"
        assert session.livekit_room == "room-live"  # untouched


# ---------------------------------------------------------------------------
# call.hangup — closes open sessions (safety net)
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
        assert session.status == "ended"


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
    """If multiple open sessions for same caller, only the latest is closed."""
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


async def test_hangup_by_call_control_id_takes_priority(in_memory_db):
    """
    If call_control_id is in the payload and matches a session,
    that session is closed even if another open session exists for the same caller.
    """
    caller = "+441234567890"
    async with in_memory_db() as db:
        db.add(CallSession(
            id="ctrl-target",
            caller_number=caller,
            livekit_room="room-target",
            started_at=datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
        ))
        db.add(CallSession(
            id="ctrl-other",
            caller_number=caller,
            livekit_room="room-other",
            started_at=datetime(2026, 1, 1, 11, 0, 0, tzinfo=timezone.utc),
        ))
        await db.commit()

    payload = {
        "call_control_id": "ctrl-target",
        "from": caller,
        "hangup_cause": "normal_clearing",
        "call_duration_ms": 10000,
    }
    client.post("/webhook/telnyx", content=_event("call.hangup", payload))

    async with in_memory_db() as db:
        target = await db.get(CallSession, "ctrl-target")
        other = await db.get(CallSession, "ctrl-other")
        assert target.ended_at is not None  # closed by call_control_id match
        assert other.ended_at is None       # untouched


# ---------------------------------------------------------------------------
# Ed25519 signature verification (unit tests — no real crypto keys needed)
# ---------------------------------------------------------------------------

def test_verify_signature_skipped_when_no_public_key(monkeypatch):
    """When TELNYX_WEBHOOK_PUBLIC_KEY is empty, verification is skipped (dev mode)."""
    monkeypatch.setenv("TELNYX_WEBHOOK_PUBLIC_KEY", "")
    monkeypatch.setenv("APP_ENV", "production")
    # Reload settings to pick up env changes
    from app.core.config import reload_settings
    reload_settings()

    payload = {"call_control_id": "x", "from": "+441234567890", "direction": "incoming"}
    resp = client.post("/webhook/telnyx", content=_event("call.initiated", payload))
    # No 401 — key is empty so verification is skipped
    assert resp.status_code == 200


def test_verify_signature_rejects_bad_signature(monkeypatch):
    """In production with a public key set, a bad signature returns 401."""
    # Use a real Ed25519 key pair generated for this test
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    import base64

    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    pub_bytes = pub.public_bytes(Encoding.Raw, PublicFormat.Raw)
    pub_b64 = base64.b64encode(pub_bytes).decode()

    monkeypatch.setenv("TELNYX_WEBHOOK_PUBLIC_KEY", pub_b64)
    monkeypatch.setenv("APP_ENV", "production")
    from app.core.config import reload_settings
    reload_settings()

    resp = client.post(
        "/webhook/telnyx",
        content=_event("call.initiated", {"from": "+44", "direction": "incoming"}),
        headers={
            "telnyx-signature-ed25519": "invalidsignature==",
            "telnyx-timestamp": "1234567890",
        },
    )
    assert resp.status_code == 401
