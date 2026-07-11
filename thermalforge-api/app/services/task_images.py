from typing import Literal, cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import ArtifactKind, QualityStatus
from app.domain.errors import EntityNotFound
from app.imaging.schemas import TaskImageAsset, TaskImageManifest
from app.models import ArtifactModel
from app.repositories.artifacts import ArtifactRepository
from app.services.tasks import TaskService

_IMAGE_KINDS = {
    ArtifactKind.CONCEPT_IMAGE.value,
    ArtifactKind.MULTIVIEW_IMAGE.value,
}


class TaskImageService:
    def __init__(self, session: AsyncSession) -> None:
        self._artifacts = ArtifactRepository(session)
        self._tasks = TaskService(session)

    async def get_manifest(self, task_id: str) -> TaskImageManifest:
        await self._tasks.get_task(task_id)
        artifacts = [
            artifact
            for artifact in await self._artifacts.list_for_task(task_id)
            if artifact.kind in _IMAGE_KINDS
            and artifact.quality_status == QualityStatus.APPROVED.value
            and isinstance(artifact.metadata_json.get("view_id"), str)
        ]
        artifacts.sort(
            key=lambda artifact: (
                self._sequence(artifact),
                artifact.created_at,
            )
        )
        if not artifacts:
            raise EntityNotFound("image_manifest", task_id)
        return TaskImageManifest(
            task_id=task_id,
            images=[self._to_asset(task_id, artifact) for artifact in artifacts],
        )

    async def get_downloadable_image(
        self,
        *,
        task_id: str,
        artifact_id: str,
    ) -> ArtifactModel:
        await self._tasks.get_task(task_id)
        artifact = await self._artifacts.get_for_task(
            task_id=task_id,
            artifact_id=artifact_id,
        )
        if (
            artifact is None
            or artifact.kind not in _IMAGE_KINDS
            or artifact.quality_status != QualityStatus.APPROVED.value
            or artifact.mime_type != "image/png"
        ):
            raise EntityNotFound("image", artifact_id)
        return artifact

    @staticmethod
    def _sequence(artifact: ArtifactModel) -> int:
        value = artifact.metadata_json.get("sequence")
        return value if isinstance(value, int) and not isinstance(value, bool) else 999

    @staticmethod
    def _to_asset(task_id: str, artifact: ArtifactModel) -> TaskImageAsset:
        return TaskImageAsset(
            artifact_id=artifact.id,
            kind=cast(
                Literal["concept_image", "multiview_image"],
                artifact.kind,
            ),
            view_id=str(artifact.metadata_json["view_id"]),
            url=f"/v1/tasks/{task_id}/images/{artifact.id}/content",
            mime_type="image/png",
            sha256=artifact.sha256,
            size_bytes=artifact.size_bytes,
            provider=artifact.provider,
            provider_model=artifact.provider_model,
        )
