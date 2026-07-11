from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_artifact_store, get_session
from app.imaging.schemas import TaskImageManifest
from app.services.artifacts.base import ArtifactStore
from app.services.task_images import TaskImageService

router = APIRouter(prefix="/v1/tasks", tags=["images"])


@router.get("/{task_id}/image-manifest", response_model=TaskImageManifest)
async def get_task_image_manifest(
    task_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TaskImageManifest:
    return await TaskImageService(session).get_manifest(task_id)


@router.get(
    "/{task_id}/images/{artifact_id}/content",
    response_class=Response,
    responses={
        200: {
            "description": "Immutable generated concept image bytes.",
            "content": {"image/png": {}},
        }
    },
)
async def download_task_image(
    task_id: str,
    artifact_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    artifact_store: Annotated[ArtifactStore, Depends(get_artifact_store)],
) -> Response:
    artifact = await TaskImageService(session).get_downloadable_image(
        task_id=task_id,
        artifact_id=artifact_id,
    )
    payload = await artifact_store.read_bytes(artifact.storage_uri)
    return Response(
        content=payload,
        media_type=artifact.mime_type,
        headers={
            "Cache-Control": "private, max-age=31536000, immutable",
            "Content-Disposition": f'inline; filename="{artifact.id}.png"',
            "ETag": f'"{artifact.sha256}"',
            "X-Content-Type-Options": "nosniff",
        },
    )
