from typing import Annotated

from fastapi import APIRouter, Depends, Response
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_application_settings,
    get_artifact_store,
    get_session,
)
from app.config import Settings
from app.services.artifacts.base import ArtifactStore
from app.services.viewer import ViewerLibraryService, ViewerService
from app.viewer.schemas import ViewerLibrary, ViewerManifest

router = APIRouter(prefix="/v1/tasks", tags=["viewer"])
library_router = APIRouter(prefix="/v1/viewer-library", tags=["viewer"])


@library_router.get("", response_model=ViewerLibrary)
def get_viewer_library(
    settings: Annotated[Settings, Depends(get_application_settings)],
) -> ViewerLibrary:
    return ViewerLibraryService(settings).get_library()


@library_router.get(
    "/{model_id}/content",
    response_class=FileResponse,
    responses={
        200: {
            "description": "Immutable curated viewer model bytes.",
            "content": {"model/gltf-binary": {}},
        }
    },
)
def download_viewer_library_model(
    model_id: str,
    settings: Annotated[Settings, Depends(get_application_settings)],
) -> FileResponse:
    path, asset = ViewerLibraryService(settings).get_model_path(model_id)
    return FileResponse(
        path=path,
        media_type=asset.mime_type,
        filename=path.name,
        content_disposition_type="inline",
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "ETag": f'"{asset.sha256}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/{task_id}/viewer-manifest", response_model=ViewerManifest)
async def get_viewer_manifest(
    task_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ViewerManifest:
    return await ViewerService(session).get_manifest(task_id)


@router.get(
    "/{task_id}/models/{artifact_id}/content",
    response_class=Response,
    responses={
        200: {
            "description": "Immutable model artifact bytes.",
            "content": {"application/octet-stream": {}},
        }
    },
)
async def download_viewer_model(
    task_id: str,
    artifact_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    artifact_store: Annotated[ArtifactStore, Depends(get_artifact_store)],
) -> Response:
    artifact = await ViewerService(session).get_downloadable_model(
        task_id=task_id,
        artifact_id=artifact_id,
    )
    payload = await artifact_store.read_bytes(artifact.storage_uri)
    filename = f"model-{artifact.id}"
    return Response(
        content=payload,
        media_type=artifact.mime_type,
        headers={
            "Cache-Control": "private, max-age=31536000, immutable",
            "Content-Disposition": f'inline; filename="{filename}"',
            "ETag": f'"{artifact.sha256}"',
            "X-Content-Type-Options": "nosniff",
        },
    )
