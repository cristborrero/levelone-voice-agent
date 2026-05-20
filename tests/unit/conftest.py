"""
Shared test fixtures for unit tests.

auth_headers — injects a valid JWT token so API tests work after auth was added.
"""
from __future__ import annotations

import os

import pytest

# Must be set before any app import
os.environ.setdefault("OPENAI_API_KEY", "test")
os.environ.setdefault("GROQ_API_KEY", "test")
os.environ.setdefault("LIVEKIT_URL", "ws://localhost:7880")
os.environ.setdefault("LIVEKIT_API_KEY", "test")
os.environ.setdefault("LIVEKIT_API_SECRET", "test")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("DASHBOARD_USERNAME", "testuser")
os.environ.setdefault("DASHBOARD_PASSWORD", "testpass")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-unit-tests-only")


@pytest.fixture()
def auth_headers() -> dict[str, str]:
    """Return Authorization headers with a fresh JWT for the test user."""
    from app.api.auth import _create_token
    token = _create_token("testuser")
    return {"Authorization": f"Bearer {token}"}
