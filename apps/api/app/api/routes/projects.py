"""`/api/v1/projects` — basic project management."""

import uuid

from fastapi import APIRouter, status

from app.api.deps import DbSession
from app.core.exceptions import NotFoundError
from app.schemas.project import ProjectCreate, ProjectRead
from app.services import project_service

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectRead])
async def list_projects(db: DbSession) -> list[ProjectRead]:
    projects = await project_service.list_projects(db)
    return [ProjectRead.model_validate(project) for project in projects]


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(data: ProjectCreate, db: DbSession) -> ProjectRead:
    project = await project_service.create_project(db, data)
    return ProjectRead.model_validate(project)


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(project_id: uuid.UUID, db: DbSession) -> ProjectRead:
    project = await project_service.get_project(db, project_id)
    if project is None:
        raise NotFoundError(f"Project '{project_id}' was not found")
    return ProjectRead.model_validate(project)
