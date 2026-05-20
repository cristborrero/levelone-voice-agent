import asyncio
from sqlalchemy import select
from app.db.session import get_session_factory
from app.db.models import DashboardUser
from app.core.config import get_settings

async def main():
    settings = get_settings()
    print("Database URL:", settings.database_url)
    factory = get_session_factory()
    async with factory() as db:
        stmt = select(DashboardUser)
        res = await db.execute(stmt)
        users = res.scalars().all()
        if not users:
            print("No users found in database!")
        for u in users:
            print(f"User ID: {u.id}, Username: {u.username}, Role: {u.role}, Hash: {u.password_hash}")

if __name__ == "__main__":
    asyncio.run(main())
