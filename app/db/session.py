from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        # check_same_thread is SQLite-only — not supported by asyncpg (PostgreSQL)
        connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
        _engine = create_async_engine(
            settings.database_url,
            echo=False,
            connect_args=connect_args,
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
    Runs synchronously — migration is a no-op when DB is already at head (~0ms).
    """
    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    # Use the synchronous SQLite URL — aiosqlite cannot be used from Alembic's runner.
    db_url = get_settings().database_url
    sync_url = db_url.replace("sqlite+aiosqlite", "sqlite").replace("sqlite+pysqlite", "sqlite")
    cfg.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(cfg, "head")





async def get_session() -> AsyncGenerator[AsyncSession, None]:
    factory = get_session_factory()
    async with factory() as session:
        yield session
