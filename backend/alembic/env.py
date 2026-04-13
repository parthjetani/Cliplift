"""Alembic environment — async-aware, reads DATABASE_URL from settings."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import settings
from app.database import Base, import_all_models

# Alembic Config object
config = context.config

# Set the SQLAlchemy URL from our app settings (NOT from alembic.ini)
# Strip the +asyncpg dialect suffix when sync, but Alembic uses async here
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Logging config from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import all models so Base.metadata is populated
import_all_models()

# Target metadata for autogenerate
target_metadata = Base.metadata


def include_object(object, name, type_, reflected, compare_to):
    """Filter out objects in the 'auth' schema (managed by Supabase)."""
    if hasattr(object, "schema") and object.schema == "auth":
        return False
    return True


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (generates SQL)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Apply migrations using a sync-style connection (Alembic requirement)."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Connect via async engine, then bridge to sync for Alembic."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online (live DB) migrations."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
