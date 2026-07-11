from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ProjectModel


class ProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, name: str) -> ProjectModel:
        project = ProjectModel(id=str(uuid4()), name=name.strip())
        self._session.add(project)
        await self._session.flush()
        return project

    async def get(self, project_id: str) -> ProjectModel | None:
        return await self._session.get(ProjectModel, project_id)
