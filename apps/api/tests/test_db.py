"""Tests for the database engine/session layer, independent of the API."""

from app.db.session import engine
from app.models.project import Project
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def test_engine_connects() -> None:
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar_one() == 1


async def test_session_persists_and_queries_a_project(db_session: AsyncSession) -> None:
    project = Project(name="ORM smoke test", description=None)
    db_session.add(project)
    await db_session.flush()

    assert project.id is not None
    assert project.created_at is not None

    fetched = await db_session.get(Project, project.id)
    assert fetched is not None
    assert fetched.name == "ORM smoke test"
