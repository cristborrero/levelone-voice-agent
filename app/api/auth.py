"""
JWT authentication for the Admin Dashboard with database-backed users & RBAC.

Endpoints:
  POST   /api/auth/login             → Returns access_token (24h JWT with role claim)
  GET    /api/auth/me                → Returns current user details (username, role)
  GET    /api/auth/users             → Lists all dashboard users (Admin only)
  POST   /api/auth/users             → Creates a new user (Admin only)
  DELETE /api/auth/users/{user_id}   → Removes a user (Admin only)
  PUT    /api/auth/users/{user_id}   → Updates username or role (Admin only / Self)
  PUT    /api/auth/users/{user_id}/password → Changes user password (Admin only / Self)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import DashboardUser
from app.db.session import get_session_factory

router = APIRouter(prefix="/api/auth", tags=["auth"])
_bearer = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Password Hashing Helpers
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verify raw password against bcrypt hash."""
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


# ---------------------------------------------------------------------------
# JWT Token Helpers
# ---------------------------------------------------------------------------

def _create_token(username: str, role: str) -> str:
    settings = get_settings()
    payload = {
        "sub": username,
        "role": role,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def _decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

class CurrentUser(BaseModel):
    id: int | None = None  # None for env-fallback if we ever skip DB
    username: str
    role: str  # admin | viewer


async def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CurrentUser:
    """FastAPI dependency — raises 401 if no valid Bearer token."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = _decode_token(credentials.credentials)
    username = payload["sub"]
    role = payload.get("role", "viewer")

    # Resolve ID from database if possible, but don't fail if we fallback
    user_id = None
    factory = get_session_factory()
    async with factory() as db:
        user = (
            await db.execute(select(DashboardUser).where(DashboardUser.username == username))
        ).scalar_one_or_none()
        if user:
            user_id = user.id
            role = user.role  # trust DB role state over token if DB claims differ

    return CurrentUser(id=user_id, username=username, role=role)


def require_admin(current_user: CurrentUser = Depends(require_auth)) -> CurrentUser:
    """FastAPI dependency — raises 403 if the user is not an admin."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Admin access required",
        )
    return current_user


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class MeResponse(BaseModel):
    id: int | None
    username: str
    role: str


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    created_at: str


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str  # admin | viewer


class UpdateUserRequest(BaseModel):
    username: str | None = None
    role: str | None = None  # admin | viewer


class ChangePasswordRequest(BaseModel):
    current_password: str | None = None  # Optional if admin is resetting, required for self-change
    new_password: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest) -> TokenResponse:
    """Validate credentials against DB (or bootstrap from env if empty) and return JWT."""
    settings = get_settings()
    factory = get_session_factory()

    async with factory() as db:
        # Check if table is empty (bootstrap scenario)
        users_count = (await db.execute(select(DashboardUser))).scalars().all()
        if not users_count:
            # First run/no users -> check if matching static env credentials
            if body.username == settings.dashboard_username and body.password == settings.dashboard_password:
                # Seed admin user
                new_admin = DashboardUser(
                    username=settings.dashboard_username,
                    password_hash=hash_password(settings.dashboard_password),
                    role="admin",
                )
                db.add(new_admin)
                await db.commit()
                
                token = _create_token(new_admin.username, new_admin.role)
                return TokenResponse(
                    access_token=token,
                    expires_in=settings.jwt_expire_hours * 3600,
                )

        # Normal authentication against DB
        user = (
            await db.execute(select(DashboardUser).where(DashboardUser.username == body.username))
        ).scalar_one_or_none()

        if user is None or not verify_password(body.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
            )

        token = _create_token(user.username, user.role)
        return TokenResponse(
            access_token=token,
            expires_in=settings.jwt_expire_hours * 3600,
        )


@router.get("/me", response_model=MeResponse)
async def me(current_user: CurrentUser = Depends(require_auth)) -> MeResponse:
    """Return current authenticated user's details."""
    return MeResponse(
        id=current_user.id,
        username=current_user.username,
        role=current_user.role,
    )


@router.get("/users", response_model=list[UserResponse])
async def list_users(admin: CurrentUser = Depends(require_admin)) -> list[UserResponse]:
    """List all registered dashboard users (Admin only)."""
    factory = get_session_factory()
    async with factory() as db:
        users = (await db.execute(select(DashboardUser).order_by(DashboardUser.id))).scalars().all()
        return [
            UserResponse(
                id=u.id,
                username=u.username,
                role=u.role,
                created_at=u.created_at.isoformat(),
            )
            for u in users
        ]


@router.post("/users", response_model=UserResponse)
async def create_user(
    body: CreateUserRequest, admin: CurrentUser = Depends(require_admin)
) -> UserResponse:
    """Create a new dashboard user (Admin only)."""
    if body.role not in ("admin", "viewer"):
        raise HTTPException(status_code=400, detail="Invalid role. Must be 'admin' or 'viewer'")

    factory = get_session_factory()
    async with factory() as db:
        # Check uniqueness
        existing = (
            await db.execute(select(DashboardUser).where(DashboardUser.username == body.username))
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail="Username already exists")

        new_user = DashboardUser(
            username=body.username,
            password_hash=hash_password(body.password),
            role=body.role,
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        
        return UserResponse(
            id=new_user.id,
            username=new_user.username,
            role=new_user.role,
            created_at=new_user.created_at.isoformat(),
        )


@router.delete("/users/{user_id}")
async def delete_user(user_id: int, admin: CurrentUser = Depends(require_admin)) -> dict[str, str]:
    """Delete a dashboard user (Admin only, cannot delete oneself)."""
    if admin.id == user_id:
        raise HTTPException(status_code=400, detail="You cannot delete yourself")

    factory = get_session_factory()
    async with factory() as db:
        user = (
            await db.execute(select(DashboardUser).where(DashboardUser.id == user_id))
        ).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        await db.delete(user)
        await db.commit()
        return {"status": "ok", "message": f"User '{user.username}' deleted"}


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int, body: UpdateUserRequest, current_user: CurrentUser = Depends(require_auth)
) -> UserResponse:
    """Update username or role (Self or Admin only)."""
    # Permission check: viewer cannot change role/username of anyone, including self
    is_self = current_user.id == user_id
    is_admin = current_user.role == "admin"
    if not (is_self or is_admin):
        raise HTTPException(status_code=403, detail="Forbidden: You cannot modify this user")

    # If updating role, only admin can do it
    if body.role is not None and not is_admin:
        raise HTTPException(status_code=403, detail="Forbidden: Only admins can change user roles")

    factory = get_session_factory()
    async with factory() as db:
        user = (
            await db.execute(select(DashboardUser).where(DashboardUser.id == user_id))
        ).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if body.username is not None and body.username != user.username:
            # Check uniqueness
            existing = (
                await db.execute(select(DashboardUser).where(DashboardUser.username == body.username))
            ).scalar_one_or_none()
            if existing:
                raise HTTPException(status_code=400, detail="Username already exists")
            user.username = body.username

        if body.role is not None:
            user.role = body.role

        await db.commit()
        await db.refresh(user)

        return UserResponse(
            id=user.id,
            username=user.username,
            role=user.role,
            created_at=user.created_at.isoformat(),
        )


@router.put("/users/{user_id}/password")
async def change_password(
    user_id: int, body: ChangePasswordRequest, current_user: CurrentUser = Depends(require_auth)
) -> dict[str, str]:
    """Change user password (Self or Admin only)."""
    is_self = current_user.id == user_id
    is_admin = current_user.role == "admin"
    
    if not (is_self or is_admin):
        raise HTTPException(status_code=403, detail="Forbidden: You cannot modify this user")

    factory = get_session_factory()
    async with factory() as db:
        user = (
            await db.execute(select(DashboardUser).where(DashboardUser.id == user_id))
        ).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Security check: if not admin, current_password must be provided and correct
        if not is_admin:
            if not body.current_password or not verify_password(body.current_password, user.password_hash):
                raise HTTPException(status_code=400, detail="Current password is incorrect")

        user.password_hash = hash_password(body.new_password)
        await db.commit()
        return {"status": "ok", "message": "Password changed successfully"}

