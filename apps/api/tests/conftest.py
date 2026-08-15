"""Shared pytest fixtures.

Tests run against a real Postgres database (see `docker-compose.yml`,
service `db`) rather than SQLite, so behavior matches production — this
matters once pgvector-backed tables show up. Crucially, they run against
a *separate* `<database>_test` database (created by
`docker/postgres/init.sql`), never the one local dev / docker-compose's
`api` service actually uses — this fixture's schema teardown would
otherwise wipe out real data. Each test additionally runs inside a
transaction that's rolled back afterwards, so tests never leak state
into one another.
"""

import os
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app


def _test_database_url() -> str:
    if explicit_url := os.environ.get("TEST_DATABASE_URL"):
        return explicit_url
    url = make_url(get_settings().database_url)
    test_url = url.set(database=f"{url.database}_test")
    # str(url) masks the password with "***" — render_as_string(hide_password=False)
    # is required to get a URL that's actually usable for connecting.
    return test_url.render_as_string(hide_password=False)


test_engine = create_async_engine(_test_database_url(), pool_pre_ping=True)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _create_schema() -> AsyncGenerator[None]:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    connection = await test_engine.connect()
    transaction = await connection.begin()
    session_factory = async_sessionmaker(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    session = session_factory()

    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    async def _get_db_override() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _get_db_override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()
