from pathlib import Path
from uuid import uuid4

import aiofiles
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.documents.validation import DocumentValidator, ValidatedDocument
from app.domain.enums import ArtifactKind, QualityStatus, TaskStatus
from app.domain.errors import (
    InvalidDocument,
    InvalidStateTransition,
    TaskAlreadyStarted,
    UploadTooLarge,
)
from app.models import ArtifactModel
from app.repositories.artifacts import ArtifactRepository
from app.repositories.tasks import TaskRepository
from app.services.artifacts.base import ArtifactStore
from app.services.tasks import TaskService


class DocumentIngestionService:
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
        self._tasks = TaskRepository(session)
        self._validator = DocumentValidator(
            max_upload_bytes=settings.max_upload_bytes,
            max_archive_entries=settings.max_archive_entries,
            max_archive_uncompressed_bytes=settings.max_archive_uncompressed_bytes,
            max_image_pixels=settings.max_image_pixels,
        )

    @staticmethod
    def _safe_filename(filename: str | None) -> str:
        leaf_name = (filename or "").replace("\\", "/").rsplit("/", maxsplit=1)[-1]
        if not leaf_name or leaf_name in {".", ".."}:
            raise InvalidDocument("Document filename is missing.")
        safe = "".join(
            character
            if character.isalnum() or character in {".", "-", "_"}
            else "_"
            for character in leaf_name
        )
        return safe[:160]

    async def _stream_to_temporary_file(
        self,
        upload: UploadFile,
        destination: Path,
    ) -> None:
        size_bytes = 0
        async with aiofiles.open(destination, "wb") as target:
            while chunk := await upload.read(self._settings.upload_chunk_bytes):
                size_bytes += len(chunk)
                if size_bytes > self._settings.max_upload_bytes:
                    raise UploadTooLarge(self._settings.max_upload_bytes)
                await target.write(chunk)

    async def _persist_document(
        self,
        *,
        task_id: str,
        validated: ValidatedDocument,
        declared_mime: str | None,
    ) -> tuple[ArtifactModel, bool]:
        existing = await self._artifacts.get_by_hash(
            task_id=task_id,
            kind=ArtifactKind.SOURCE_DOCUMENT,
            sha256=validated.sha256,
        )
        if existing is not None:
            return existing, False

        stored = await self._artifact_store.put_file(
            task_id=task_id,
            relative_path=(
                f"documents/{validated.sha256}/{validated.filename}"
            ),
            source_path=validated.path,
            mime_type=validated.mime_type,
        )
        artifact = await self._artifacts.create(
            task_id=task_id,
            kind=ArtifactKind.SOURCE_DOCUMENT,
            stored=stored,
            metadata={
                "filename": validated.filename,
                "extension": validated.extension,
                "declared_mime": declared_mime or "",
                "detected_mime": validated.mime_type,
                "content_trust": "untrusted",
            },
            quality_status=QualityStatus.APPROVED,
        )
        await self._session.commit()
        await self._session.refresh(artifact)
        return artifact, True

    async def ingest(self, task_id: str, upload: UploadFile) -> ArtifactModel:
        task_service = TaskService(self._session)
        task = await task_service.get_task_for_update(task_id)
        current_status = TaskStatus(task.status)
        if current_status not in {TaskStatus.CREATED, TaskStatus.UPLOADED}:
            raise InvalidStateTransition(
                current_status.value,
                TaskStatus.UPLOADED.value,
            )
        started_event = await self._tasks.get_latest_event(
            task_id=task_id,
            event_type="task.started",
        )
        if started_event is not None:
            raise TaskAlreadyStarted()

        safe_filename = self._safe_filename(upload.filename)
        temporary_path = self._settings.upload_temp_root / f"{uuid4().hex}.upload"
        try:
            await self._stream_to_temporary_file(upload, temporary_path)
            validated = self._validator.validate(
                path=temporary_path,
                original_filename=safe_filename,
                declared_mime=upload.content_type,
            )
            artifact, created = await self._persist_document(
                task_id=task_id,
                validated=validated,
                declared_mime=upload.content_type,
            )

            if current_status == TaskStatus.CREATED:
                await task_service.transition(
                    task_id,
                    TaskStatus.UPLOADED,
                    event_type="task.uploaded",
                    payload={"artifact_id": artifact.id},
                )
            elif created:
                await self._tasks.append_event(
                    task_id=task_id,
                    event_type="document.uploaded",
                    payload={"artifact_id": artifact.id},
                )
                await self._session.commit()
            return artifact
        finally:
            await upload.close()
            temporary_path.unlink(missing_ok=True)
