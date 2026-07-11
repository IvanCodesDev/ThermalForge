from typing import cast
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import ArtifactKind, QualityStatus
from app.models import ArtifactModel
from app.services.artifacts.base import ArtifactWriteResult


class ArtifactRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        task_id: str,
        kind: ArtifactKind,
        stored: ArtifactWriteResult,
        provider: str | None = None,
        provider_model: str | None = None,
        provider_task_id: str | None = None,
        prompt_version: str | None = None,
        metadata: dict[str, object] | None = None,
        quality_status: QualityStatus = QualityStatus.PENDING,
    ) -> ArtifactModel:
        version_statement = select(
            func.coalesce(func.max(ArtifactModel.version), 0) + 1
        ).where(
            ArtifactModel.task_id == task_id,
            ArtifactModel.kind == kind.value,
        )
        version = int((await self._session.scalar(version_statement)) or 1)
        artifact = ArtifactModel(
            id=str(uuid4()),
            task_id=task_id,
            kind=kind.value,
            version=version,
            mime_type=stored.mime_type,
            sha256=stored.sha256,
            size_bytes=stored.size_bytes,
            storage_uri=stored.storage_uri,
            provider=provider,
            provider_model=provider_model,
            provider_task_id=provider_task_id,
            prompt_version=prompt_version,
            metadata_json=metadata or {},
            quality_status=quality_status.value,
        )
        self._session.add(artifact)
        await self._session.flush()
        return artifact

    async def get_by_hash(
        self,
        *,
        task_id: str,
        kind: ArtifactKind,
        sha256: str,
    ) -> ArtifactModel | None:
        statement = select(ArtifactModel).where(
            ArtifactModel.task_id == task_id,
            ArtifactModel.kind == kind.value,
            ArtifactModel.sha256 == sha256,
        )
        return cast(ArtifactModel | None, await self._session.scalar(statement))

    async def list_for_task(self, task_id: str) -> list[ArtifactModel]:
        statement = (
            select(ArtifactModel)
            .where(ArtifactModel.task_id == task_id)
            .order_by(ArtifactModel.created_at, ArtifactModel.version)
        )
        return list((await self._session.scalars(statement)).all())

    async def get_for_task(
        self,
        *,
        task_id: str,
        artifact_id: str,
    ) -> ArtifactModel | None:
        statement = select(ArtifactModel).where(
            ArtifactModel.id == artifact_id,
            ArtifactModel.task_id == task_id,
        )
        return cast(ArtifactModel | None, await self._session.scalar(statement))

    async def get_latest_approved(
        self,
        *,
        task_id: str,
        kind: ArtifactKind,
    ) -> ArtifactModel | None:
        statement = (
            select(ArtifactModel)
            .where(
                ArtifactModel.task_id == task_id,
                ArtifactModel.kind == kind.value,
                ArtifactModel.quality_status == QualityStatus.APPROVED.value,
            )
            .order_by(ArtifactModel.version.desc(), ArtifactModel.created_at.desc())
            .limit(1)
        )
        return cast(ArtifactModel | None, await self._session.scalar(statement))
