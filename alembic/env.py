"""Alembic env.py — configured for async SQLAlchemy (asyncpg)."""

import asyncio
from logging.config import fileConfig
import ssl
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import all ORM models so Alembic can detect them for autogenerate
from shared.db.models import DatasetRecord, IngestionLog  # noqa: F401
from shared.db.session import Base
from shared.config import settings

config = context.config

# 1. Clean 'sslmode' from the database URL exactly like we do in session.py
db_url = settings.DATABASE_URL
has_ssl = "sslmode" in db_url

if has_ssl:
    parsed_url = urlparse(db_url)
    query_params = parse_qsl(parsed_url.query)
    filtered_params = [param for param in query_params if param[0] != 'sslmode']
    new_query = urlencode(filtered_params)
    db_url = urlunparse(parsed_url._replace(query=new_query))

# 2. Assign the sanitized URL to Alembic configuration
config.set_main_option("sqlalchemy.url", db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    # 3. Re-inject safe secure connection parameters for asyncpg
    connect_args = {}
    if has_ssl or "render.com" in db_url or "neon.tech" in db_url:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        connect_args["ssl"] = ctx

    # 4. Pass connect_args explicitly to the configuration generator
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,  # Injected here
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
