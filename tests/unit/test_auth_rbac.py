from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.auth import hash_password, _create_token
from app.db.models import DashboardUser
from app.db.session import get_session_factory
from app.main import create_app


@pytest.fixture()
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


@pytest.mark.asyncio
async def test_auto_bootstrap_on_empty_db(client: TestClient):
    # Ensure the DB starts clean of dashboard users for this test
    factory = get_session_factory()
    async with factory() as db:
        # Delete any existing users to trigger bootstrap
        users = (await db.execute(select(DashboardUser))).scalars().all()
        for u in users:
            await db.delete(u)
        await db.commit()

    # Login with env credentials (default in test config is testuser / testpass)
    resp = client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "testpass"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data

    # Verify a user was created in the DB as admin
    async with factory() as db:
        db_users = (await db.execute(select(DashboardUser))).scalars().all()
        assert len(db_users) == 1
        assert db_users[0].username == "testuser"
        assert db_users[0].role == "admin"


@pytest.mark.asyncio
async def test_admin_user_crud(client: TestClient):
    factory = get_session_factory()
    # Create an admin user token
    admin_token = _create_token("admin_test", role="admin")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Ensure admin_test user exists in DB sorequire_auth can resolve ID
    async with factory() as db:
        admin_db = (
            await db.execute(select(DashboardUser).where(DashboardUser.username == "admin_test"))
        ).scalar_one_or_none()
        if not admin_db:
            admin_db = DashboardUser(
                username="admin_test",
                password_hash=hash_password("adminpass"),
                role="admin",
            )
            db.add(admin_db)
            await db.commit()

    # Admin creates a viewer user
    resp = client.post(
        "/api/auth/users",
        json={"username": "viewer_test", "password": "viewerpass", "role": "viewer"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    viewer_id = resp.json()["id"]

    # Admin lists users
    resp = client.get("/api/auth/users", headers=admin_headers)
    assert resp.status_code == 200
    users = resp.json()
    usernames = [u["username"] for u in users]
    assert "viewer_test" in usernames

    # Viewer token tries to list users (should fail with 403)
    viewer_token = _create_token("viewer_test", role="viewer")
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}
    
    resp = client.get("/api/auth/users", headers=viewer_headers)
    assert resp.status_code == 403

    # Viewer tries to change own password
    resp = client.put(
        f"/api/auth/users/{viewer_id}/password",
        json={"current_password": "viewerpass", "new_password": "newviewerpass"},
        headers=viewer_headers,
    )
    assert resp.status_code == 200

    # Viewer tries to change own password with wrong current password (should fail)
    resp = client.put(
        f"/api/auth/users/{viewer_id}/password",
        json={"current_password": "wrongpass", "new_password": "newpass2"},
        headers=viewer_headers,
    )
    assert resp.status_code == 400

    # Admin deletes the viewer
    resp = client.delete(f"/api/auth/users/{viewer_id}", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_rbac_write_endpoint_restrictions(client: TestClient):
    factory = get_session_factory()
    # Ensure a viewer user exists in the DB
    async with factory() as db:
        viewer_db = (
            await db.execute(select(DashboardUser).where(DashboardUser.username == "viewer_test2"))
        ).scalar_one_or_none()
        if not viewer_db:
            viewer_db = DashboardUser(
                username="viewer_test2",
                password_hash=hash_password("viewerpass"),
                role="viewer",
            )
            db.add(viewer_db)
            await db.commit()

    viewer_token = _create_token("viewer_test2", role="viewer")
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

    # Viewer tries to update LLM configuration (should fail with 403)
    resp = client.put(
        "/api/config/llm/main_agent",
        json={"provider": "openai", "model": "gpt-4o"},
        headers=viewer_headers,
    )
    assert resp.status_code == 403

    # Viewer tries to run provider connectivity test (should fail with 403)
    resp = client.post(
        "/api/providers/openai/test",
        headers=viewer_headers,
    )
    assert resp.status_code == 403
