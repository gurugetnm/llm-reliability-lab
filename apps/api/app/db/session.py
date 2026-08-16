"""Async SQLAlchemy engine/session setup."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.database_url, pool_pre_ping=True)

AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession]:
    """FastAPI dependency yielding a request-scoped database session.

    Commits once the route handler returns without raising, and rolls
    back otherwise — the standard "commit on success" request-scoped
    session pattern. Without this, `session.close()` alone rolls back
    anything that was only `flush()`ed (never `commit()`ted), so any
    service that relies on this dependency for durability rather than
    calling `db.commit()` itself — most of the experiment engine's
    services — would silently lose every write once the request ends.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
