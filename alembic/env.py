"""
Alembic environment — synchronous SQLAlchemy setup.

DATABASE_URL is read from the app Settings (respects .env file).
Run migrations:
  uv run alembic upgrade head
Generate a new migration:
  uv run alembic revision --autogenerate -m "describe change"
"""
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection

from alembic import context

# ---------------------------------------------------------------------------
# App imports — bring in models and settings
# ---------------------------------------------------------------------------
from app.core.config import get_settings
from app.db.models import Base  # noqa: F401 — needed for autogenerate

config = context.config
settings = get_settings()

# Alembic uses a synchronous engine — strip async driver prefix so it never
# tries to run asyncio.run() which deadlocks inside asyncio.to_thread().
_db_url = settings.database_url
_sync_url = _db_url.replace("sqlite+aiosqlite", "sqlite").replace("sqlite+pysqlite", "sqlite")
config.set_main_option("sqlalchemy.url", _sync_url)

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
# Online mode — synchronous engine (no asyncio, no deadlock risk)
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


def run_migrations_online() -> None:
    from sqlalchemy import engine_from_config

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        do_run_migrations(connection)
    connectable.dispose()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
