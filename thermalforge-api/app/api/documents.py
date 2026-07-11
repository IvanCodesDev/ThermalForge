from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_application_settings,
    get_artifact_store,
    get_session,
)
from app.config import Settings
from app.domain.schemas import ArtifactRead
from app.services.artifacts.base import ArtifactStore
from app.services.document_ingestion import DocumentIngestionService

router = APIRouter(prefix="/v1/tasks", tags=["documents"])


@router.post(
    "/{task_id}/documents",
    response_model=ArtifactRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    task_id: str,
    file: Annotated[UploadFile, File()],
    session: Annotated[AsyncSession, Depends(get_session)],
    artifact_store: Annotated[ArtifactStore, Depends(get_artifact_store)],
    settings: Annotated[Settings, Depends(get_application_settings)],
) -> ArtifactRead:
    artifact = await DocumentIngestionService(
        session=session,
        artifact_store=artifact_store,
        settings=settings,
    ).ingest(task_id, file)
    return ArtifactRead.model_validate(artifact)
