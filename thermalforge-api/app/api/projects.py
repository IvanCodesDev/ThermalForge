from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session
from app.domain.schemas import ProjectCreate, ProjectRead
from app.repositories.projects import ProjectRepository

router = APIRouter(prefix="/v1/projects", tags=["projects"])


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    request: ProjectCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProjectRead:
    repository = ProjectRepository(session)
    project = await repository.create(request.name)
    await session.commit()
    await session.refresh(project)
    return ProjectRead.model_validate(project)
