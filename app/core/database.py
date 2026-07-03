from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from app.core.config import get_settings

settings = get_settings()

# Async engine for FastAPI
async_engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

# Sync engine for migrations / init scripts
sync_engine = create_engine(
    settings.sync_database_url,
    pool_pre_ping=True,
)

SyncSessionLocal = sessionmaker(bind=sync_engine)

Base = declarative_base()


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
