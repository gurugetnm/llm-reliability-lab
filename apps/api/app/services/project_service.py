"""Business logic for projects, kept separate from HTTP concerns.

Routes translate HTTP <-> schemas and delegate everything else here, so
this logic is reusable from a future CLI, background job, or test
without importing FastAPI.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.schemas.project import ProjectCreate


async def create_project(db: AsyncSession, data: ProjectCreate) -> Project:
    project = Project(name=data.name, description=data.description)
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


async def list_projects(db: AsyncSession) -> list[Project]:
    result = await db.execute(select(Project).order_by(Project.created_at.desc()))
    return list(result.scalars().all())


async def get_project(db: AsyncSession, project_id: uuid.UUID) -> Project | None:
    return await db.get(Project, project_id)
