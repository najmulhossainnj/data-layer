from contextlib import asynccontextmanager
from typing import AsyncGenerator
import ssl

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from shared.config import settings

# 1. Intercept and clean the connection string
db_url = settings.DATABASE_URL
has_ssl = "sslmode=" in db_url

if has_ssl:
    # Chop off '?sslmode=...' so asyncpg doesn't crash on keywords
    db_url = db_url.split("?")[0]

# 2. Re-inject safe secure connection parameters
connect_args = {}
if has_ssl:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    connect_args["ssl"] = ctx

# 3. Create engine with sanitized parameters and your original pool settings
engine = create_async_engine(
    db_url,
    echo=settings.APP_ENV == "development",
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,          # detect stale connections
    connect_args=connect_args,   # Injected here
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Context manager that yields a DB session and handles commit / rollback."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a session."""
    async with AsyncSessionLocal() as session:
        yield session
