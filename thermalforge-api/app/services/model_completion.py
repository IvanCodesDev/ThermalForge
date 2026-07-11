from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.domain.enums import ArtifactKind, QualityStatus, TaskStatus
from app.domain.errors import DomainError, ModelAssetUnavailable
from app.models import ArtifactModel
from app.repositories.artifacts import ArtifactRepository
from app.services.artifacts.base import ArtifactStore
from app.services.tasks import TaskService

_PROVIDER_MODEL = "curated-foc-reference-v1"
_SEGMENT_NODE_NAMES = ["root.0", "root.1", "root.2"]


class ModelCompletionService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        artifact_store: ArtifactStore,
        settings: Settings,
    ) -> None:
        self._session = session
        self._artifact_store = artifact_store
        self._settings = settings
        self._artifacts = ArtifactRepository(session)
        self._tasks = TaskService(session)

    async def complete(self, task_id: str) -> None:
        try:
            whole_path = self._resolve_model(self._settings.whole_model_filename)
            segmented_path = self._resolve_model(
                self._settings.segmented_model_filename
            )

            task = await self._tasks.get_task(task_id)
            status = TaskStatus(task.status)
            if status == TaskStatus.MODELING:
                raw_model = await self._persist_model(
                    task_id=task_id,
                    kind=ArtifactKind.RAW_MODEL,
                    source_path=whole_path,
                    variant="whole",
                    node_names=[],
                )
                normalized_model = await self._persist_model(
                    task_id=task_id,
                    kind=ArtifactKind.NORMALIZED_MODEL,
                    source_path=segmented_path,
                    variant="segmented",
                    node_names=_SEGMENT_NODE_NAMES,
                )
                await self._tasks.transition(
                    task_id,
                    TaskStatus.MODEL_REVIEW,
                    event_type="model.reference_associated",
                    payload={
                        "artifact_ids": [raw_model.id, normalized_model.id],
                        "source": "curated_reference",
                    },
                )
                status = TaskStatus.MODEL_REVIEW

            if status == TaskStatus.MODEL_REVIEW:
                await self._tasks.transition(
                    task_id,
                    TaskStatus.READY,
                    event_type="task.ready",
                    payload={"model_fidelity": "curated_concept_reference"},
                )
        except Exception as error:
            await self._mark_failed(task_id, error)
            if isinstance(error, DomainError):
                raise
            raise ModelAssetUnavailable() from error

    def _resolve_model(self, filename: str) -> Path:
        root = self._settings.model_asset_root.resolve()
        candidate = (root / filename).resolve()
        if (
            not candidate.is_relative_to(root)
            or candidate.suffix.lower() != ".glb"
            or not candidate.is_file()
        ):
            raise ModelAssetUnavailable()
        return candidate

    async def _persist_model(
        self,
        *,
        task_id: str,
        kind: ArtifactKind,
        source_path: Path,
        variant: str,
        node_names: list[str],
    ) -> ArtifactModel:
        stored = await self._artifact_store.put_file(
            task_id=task_id,
            relative_path=f"models/{variant}/{source_path.name}",
            source_path=source_path,
            mime_type="model/gltf-binary",
        )
        existing = await self._artifacts.get_by_hash(
            task_id=task_id,
            kind=kind,
            sha256=stored.sha256,
        )
        if existing is not None:
            return existing

        artifact = await self._artifacts.create(
            task_id=task_id,
            kind=kind,
            stored=stored,
            provider="thermalforge",
            provider_model=_PROVIDER_MODEL,
            metadata={
                "filename": source_path.name,
                "format": "glb",
                "source": "curated_reference",
                "fidelity": "concept_mesh",
                "manufacturable_cad": False,
                "variant": variant,
                "node_names": node_names,
            },
            quality_status=QualityStatus.APPROVED,
        )
        await self._session.commit()
        await self._session.refresh(artifact)
        return artifact

    async def _mark_failed(self, task_id: str, error: Exception) -> None:
        task = await self._tasks.get_task(task_id)
        status = TaskStatus(task.status)
        if status in {TaskStatus.READY, TaskStatus.FAILED, TaskStatus.CANCELLED}:
            return
        code = (
            error.code if isinstance(error, DomainError) else "model_asset_unavailable"
        )
        await self._tasks.transition(
            task_id,
            TaskStatus.FAILED,
            event_type="model.completion.failed",
            payload={"code": code},
        )
