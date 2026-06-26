from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from app.config import settings
from app.logging_config import logger

# Initialize async engine for Postgres
engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=10,
    max_overflow=20
)

# Async session factory
async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Base class for SQLAlchemy models
class Base(DeclarativeBase):
    pass

# Dependency to get db session in FastAPI routes
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session

# Database connection health check helper
async def check_db_connection() -> bool:
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
            return True
    except Exception as e:
        logger.error(f"PostgreSQL connection check failed: {e}")
        return False
