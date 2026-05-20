"""
Alembic environment — async SQLAlchemy setup.

DATABASE_URL is read from the app Settings (respects .env file).
Run migrations:
  uv run alembic upgrade head
Generate a new migration:
  uv run alembic revision --autogenerate -m "describe change"
"""
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ---------------------------------------------------------------------------
# App imports — bring in models and settings
# ---------------------------------------------------------------------------
from app.core.config import get_settings
from app.db.models import Base  # noqa: F401 — needed for autogenerate

config = context.config
settings = get_settings()

# Override sqlalchemy.url from our pydantic Settings so we have one source of truth
config.set_main_option("sqlalchemy.url", settings.database_url)

# Set up Python logging from alembic.ini (only if running as CLI)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Offline mode (generates SQL without a live DB connection)
# ---------------------------------------------------------------------------
def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    is_sqlite = url.startswith("sqlite")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=is_sqlite,  # SQLite needs batch mode for ALTER TABLE
    )
    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online mode (async engine)
# ---------------------------------------------------------------------------
def do_run_migrations(connection: Connection) -> None:
    is_sqlite = connection.dialect.name == "sqlite"
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=is_sqlite,  # SQLite needs batch mode for ALTER TABLE
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
