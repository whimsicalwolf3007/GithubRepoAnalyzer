"""
Async PostgreSQL database setup with SQLAlchemy.
"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

# Normalize DATABASE_URL for asyncpg compatibility with Neon:
# - Ensure the driver prefix is postgresql+asyncpg
# - Convert sslmode → ssl (asyncpg naming)
# - Strip params asyncpg doesn't support (e.g. channel_binding)
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

_ASYNCPG_UNSUPPORTED_PARAMS = {"channel_binding"}

def _normalize_db_url(url: str) -> str:
    # Fix driver prefix
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    elif url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://"):]

    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)

    # Convert sslmode → ssl
    if "sslmode" in params:
        params["ssl"] = params.pop("sslmode")

    # Remove unsupported params
    for key in _ASYNCPG_UNSUPPORTED_PARAMS:
        params.pop(key, None)

    # Rebuild query string (single values, not lists)
    clean_query = urlencode({k: v[0] for k, v in params.items()})
    return urlunparse(parsed._replace(query=clean_query))

_db_url = _normalize_db_url(settings.DATABASE_URL)

# Create async engine for PostgreSQL
engine = create_async_engine(
    _db_url,
    echo=False,
    pool_size=5,
    max_overflow=10,
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


async def get_db() -> AsyncSession:
    """Dependency that provides an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Create all database tables on startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
