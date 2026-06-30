"""
Async PostgreSQL database setup with SQLAlchemy.
"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

# Normalize DATABASE_URL for asyncpg:
# 1. Ensure the driver is postgresql+asyncpg (not postgresql or postgres)
# 2. Convert sslmode= to ssl= (asyncpg uses 'ssl', not 'sslmode')
_db_url = settings.DATABASE_URL
if _db_url.startswith("postgresql+asyncpg://"):
    pass  # Already correct
elif _db_url.startswith("postgresql://"):
    _db_url = _db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql+asyncpg://", 1)
_db_url = _db_url.replace("sslmode=", "ssl=")

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
