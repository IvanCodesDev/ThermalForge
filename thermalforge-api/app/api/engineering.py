from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_artifact_store, get_session
from app.domain.enums import ArtifactKind
from app.domain.errors import EntityNotFound
from app.engineering.schemas import EngineeringBrief
from app.repositories.artifacts import ArtifactRepository
from app.services.artifacts.base import ArtifactStore
from app.services.tasks import TaskService

router = APIRouter(prefix="/v1/tasks", tags=["engineering"])


@router.get("/{task_id}/engineering-brief", response_model=EngineeringBrief)
async def get_engineering_brief(
    task_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    artifact_store: Annotated[ArtifactStore, Depends(get_artifact_store)],
) -> EngineeringBrief:
    await TaskService(session).get_task(task_id)
    artifacts = await ArtifactRepository(session).list_for_task(task_id)
    artifact = next(
        (
            candidate
            for candidate in reversed(artifacts)
            if candidate.kind == ArtifactKind.ENGINEERING_BRIEF.value
        ),
        None,
    )
    if artifact is None:
        raise EntityNotFound("EngineeringBrief", task_id)
    payload = await artifact_store.read_bytes(artifact.storage_uri)
    return EngineeringBrief.model_validate_json(payload)
