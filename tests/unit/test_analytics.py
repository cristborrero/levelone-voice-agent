"""Unit tests for analytics endpoints — real SQLite in-memory DB."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("OPENAI_API_KEY", "test")
os.environ.setdefault("GROQ_API_KEY", "test")
os.environ.setdefault("LIVEKIT_URL", "ws://localhost:7880")
os.environ.setdefault("LIVEKIT_API_KEY", "test")
os.environ.setdefault("LIVEKIT_API_SECRET", "test")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from app.db.models import Base, CallSession  # noqa: E402
from app.db.session import get_session_factory  # noqa: E402
from app.main import create_app  # noqa: E402

app = create_app()


# ---------------------------------------------------------------------------
# In-memory DB fixture
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
async def in_memory_db(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr("app.db.session._session_factory", factory)
    monkeypatch.setattr("app.api.admin.get_session_factory", lambda: factory)


async def _insert_sessions(factory: async_sessionmaker, sessions: list[dict]) -> None:
    async with factory() as db:
        for s in sessions:
            db.add(CallSession(**s))
        await db.commit()


# ---------------------------------------------------------------------------
# _derive_outcome
# ---------------------------------------------------------------------------

class TestDeriveOutcome:
    def test_booked(self) -> None:
        from app.api.admin import _derive_outcome
        assert _derive_outcome("uid-123", None) == "meeting_booked"

    def test_follow_up_hot(self) -> None:
        from app.api.admin import _derive_outcome
        assert _derive_outcome(None, "hot") == "follow_up"

    def test_follow_up_warm(self) -> None:
        from app.api.admin import _derive_outcome
        assert _derive_outcome(None, "warm") == "follow_up"

    def test_not_qualified_cold(self) -> None:
        from app.api.admin import _derive_outcome
        assert _derive_outcome(None, "cold") == "not_qualified"

    def test_not_qualified_unqualified(self) -> None:
        from app.api.admin import _derive_outcome
        assert _derive_outcome(None, "unqualified") == "not_qualified"

    def test_info_only_no_score(self) -> None:
        from app.api.admin import _derive_outcome
        assert _derive_outcome(None, None) == "info_only"

    def test_booking_overrides_lead_score(self) -> None:
        from app.api.admin import _derive_outcome
        assert _derive_outcome("uid-123", "cold") == "meeting_booked"


# ---------------------------------------------------------------------------
# GET /api/analytics/overview
# ---------------------------------------------------------------------------

class TestAnalyticsOverview:
    async def test_empty_db_returns_zeros(self, in_memory_db: None, auth_headers: dict) -> None:
        from app.api.admin import get_session_factory as _gsf
        client = TestClient(app)
        resp = client.get("/api/analytics/overview", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_calls_7d"] == 0
        assert data["total_bookings_7d"] == 0
        assert data["conversion_rate"] == 0
        assert len(data["calls_by_day"]) == 7

    async def test_counts_calls_within_7_days(self, in_memory_db: None, auth_headers: dict) -> None:
        from app.db.session import get_session_factory as gsf
        now = datetime.now(timezone.utc)
        await _insert_sessions(gsf(), [
            {"id": "c1", "caller_number": "+441", "livekit_room": "r1",
             "started_at": now - timedelta(days=1), "calcom_booking_uid": "uid-1"},
            {"id": "c2", "caller_number": "+442", "livekit_room": "r2",
             "started_at": now - timedelta(days=2), "lead_score": "hot"},
            # outside window — should not count
            {"id": "c3", "caller_number": "+443", "livekit_room": "r3",
             "started_at": now - timedelta(days=8)},
        ])

        client = TestClient(app)
        resp = client.get("/api/analytics/overview", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_calls_7d"] == 2
        assert data["total_bookings_7d"] == 1

    async def test_conversion_rate_calculation(self, in_memory_db: None, auth_headers: dict) -> None:
        from app.db.session import get_session_factory as gsf
        now = datetime.now(timezone.utc)
        await _insert_sessions(gsf(), [
            {"id": "c1", "caller_number": "+441", "livekit_room": "r1",
             "started_at": now - timedelta(days=1), "calcom_booking_uid": "uid-1",
             "duration_seconds": 300},
            {"id": "c2", "caller_number": "+442", "livekit_room": "r2",
             "started_at": now - timedelta(days=1), "duration_seconds": 120},
            {"id": "c3", "caller_number": "+443", "livekit_room": "r3",
             "started_at": now - timedelta(days=1), "duration_seconds": 180},
            {"id": "c4", "caller_number": "+444", "livekit_room": "r4",
             "started_at": now - timedelta(days=1), "calcom_booking_uid": "uid-2",
             "duration_seconds": 420},
        ])

        client = TestClient(app)
        resp = client.get("/api/analytics/overview", headers=auth_headers)
        data = resp.json()
        assert data["total_calls_7d"] == 4
        assert data["total_bookings_7d"] == 2
        assert data["conversion_rate"] == 50.0

    async def test_outcome_counts_in_top_outcomes(self, in_memory_db: None, auth_headers: dict) -> None:
        from app.db.session import get_session_factory as gsf
        now = datetime.now(timezone.utc)
        await _insert_sessions(gsf(), [
            {"id": "c1", "caller_number": "+1", "livekit_room": "r1",
             "started_at": now - timedelta(days=1), "calcom_booking_uid": "uid"},
            {"id": "c2", "caller_number": "+2", "livekit_room": "r2",
             "started_at": now - timedelta(days=1), "lead_score": "warm"},
            {"id": "c3", "caller_number": "+3", "livekit_room": "r3",
             "started_at": now - timedelta(days=1), "lead_score": "cold"},
            {"id": "c4", "caller_number": "+4", "livekit_room": "r4",
             "started_at": now - timedelta(days=1)},
        ])

        client = TestClient(app)
        data = client.get("/api/analytics/overview", headers=auth_headers).json()
        outcomes = {o["label"]: o["count"] for o in data["top_outcomes"]}
        assert outcomes["Meeting Booked"] == 1
        assert outcomes["Follow-up"] == 1
        assert outcomes["Not Qualified"] == 1
        assert outcomes["Info Only"] == 1


# ---------------------------------------------------------------------------
# GET /api/analytics/calls
# ---------------------------------------------------------------------------

class TestRecentCalls:
    async def test_empty_db_returns_empty_list(self, in_memory_db: None, auth_headers: dict) -> None:
        client = TestClient(app)
        resp = client.get("/api/analytics/calls", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == {"calls": [], "total": 0}

    async def test_returns_real_sessions(self, in_memory_db: None, auth_headers: dict) -> None:
        from app.db.session import get_session_factory as gsf
        now = datetime.now(timezone.utc)
        await _insert_sessions(gsf(), [
            {"id": "c1", "caller_number": "+447911123456", "livekit_room": "r1",
             "started_at": now - timedelta(hours=1), "calcom_booking_uid": "uid-1",
             "duration_seconds": 245},
        ])

        client = TestClient(app)
        data = client.get("/api/analytics/calls", headers=auth_headers).json()
        assert data["total"] == 1
        call = data["calls"][0]
        assert call["id"] == "c1"
        assert call["caller_name"] == "+447911123456"
        assert call["outcome"] == "meeting_booked"
        assert call["booked"] is True
        assert call["duration_formatted"] == "4m 05s"

    async def test_capped_at_12_records(self, in_memory_db: None, auth_headers: dict) -> None:
        from app.db.session import get_session_factory as gsf
        now = datetime.now(timezone.utc)
        await _insert_sessions(gsf(), [
            {"id": f"c{i}", "caller_number": f"+44{i}", "livekit_room": f"r{i}",
             "started_at": now - timedelta(hours=i)}
            for i in range(15)
        ])

        client = TestClient(app)
        data = client.get("/api/analytics/calls", headers=auth_headers).json()
        assert data["total"] == 12

    async def test_ordered_most_recent_first(self, in_memory_db: None, auth_headers: dict) -> None:
        from app.db.session import get_session_factory as gsf
        now = datetime.now(timezone.utc)
        await _insert_sessions(gsf(), [
            {"id": "old", "caller_number": "+441", "livekit_room": "r1",
             "started_at": now - timedelta(hours=5)},
            {"id": "new", "caller_number": "+442", "livekit_room": "r2",
             "started_at": now - timedelta(hours=1)},
        ])

        client = TestClient(app)
        calls = client.get("/api/analytics/calls", headers=auth_headers).json()["calls"]
        assert calls[0]["id"] == "new"
        assert calls[1]["id"] == "old"
