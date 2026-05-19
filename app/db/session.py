from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=False,
            connect_args={"check_same_thread": False},
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=_get_engine(),
            expire_on_commit=False,
        )
    return _session_factory


async def init_db() -> None:
    """
    Apply all pending Alembic migrations at startup.
    Safe to call on every startup — Alembic tracks applied revisions.
    """
    import asyncio
    from alembic import command
    from alembic.config import Config

    def _run_migrations() -> None:
        cfg = Config("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", get_settings().database_url)
        command.upgrade(cfg, "head")

    # Run in a thread to avoid blocking the event loop
    await asyncio.to_thread(_run_migrations)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    factory = get_session_factory()
    async with factory() as session:
        yield session
