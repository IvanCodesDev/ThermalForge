from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_artifact_store, get_session
from app.domain.enums import ArtifactKind
from app.domain.errors import EntityNotFound
from app.repositories.artifacts import ArtifactRepository
from app.services.artifacts.base import ArtifactStore
from app.services.tasks import TaskService
from app.thermal.schemas import ThermalAnalysisResult, ThermalDesignSpec

router = APIRouter(prefix="/v1/tasks", tags=["thermal-design"])


async def _read_latest[ArtifactSchema: BaseModel](
    *,
    task_id: str,
    kind: ArtifactKind,
    schema: type[ArtifactSchema],
    session: AsyncSession,
    artifact_store: ArtifactStore,
) -> ArtifactSchema:
    await TaskService(session).get_task(task_id)
    artifacts = await ArtifactRepository(session).list_for_task(task_id)
    artifact = next(
        (
            candidate
            for candidate in reversed(artifacts)
            if candidate.kind == kind.value
        ),
        None,
    )
    if artifact is None:
        raise EntityNotFound(kind.value, task_id)
    payload = await artifact_store.read_bytes(artifact.storage_uri)
    return schema.model_validate_json(payload)


@router.get(
    "/{task_id}/thermal-analysis",
    response_model=ThermalAnalysisResult,
)
async def get_thermal_analysis(
    task_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    artifact_store: Annotated[ArtifactStore, Depends(get_artifact_store)],
) -> ThermalAnalysisResult:
    return await _read_latest(
        task_id=task_id,
        kind=ArtifactKind.THERMAL_ANALYSIS,
        schema=ThermalAnalysisResult,
        session=session,
        artifact_store=artifact_store,
    )


@router.get(
    "/{task_id}/thermal-design",
    response_model=ThermalDesignSpec,
)
async def get_thermal_design(
    task_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    artifact_store: Annotated[ArtifactStore, Depends(get_artifact_store)],
) -> ThermalDesignSpec:
    return await _read_latest(
        task_id=task_id,
        kind=ArtifactKind.THERMAL_DESIGN,
        schema=ThermalDesignSpec,
        session=session,
        artifact_store=artifact_store,
    )
