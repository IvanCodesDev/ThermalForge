from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

import aiofiles
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.documents.ocr import OcrProvider
from app.documents.parsers import DocumentParserRegistry
from app.documents.schemas import DocumentBundle, DocumentSource
from app.documents.validation import DocumentValidator
from app.domain.enums import ArtifactKind, QualityStatus, TaskStatus
from app.domain.errors import (
    DocumentProcessingFailed,
    DomainError,
    InvalidDocument,
    InvalidStateTransition,
)
from app.models import ArtifactModel
from app.repositories.artifacts import ArtifactRepository
from app.repositories.stage_runs import StageRunRepository
from app.services.artifacts.base import ArtifactStore
from app.services.tasks import TaskService


class DocumentProcessingService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        artifact_store: ArtifactStore,
        ocr_provider: OcrProvider,
        settings: Settings,
    ) -> None:
        self._session = session
        self._artifact_store = artifact_store
        self._settings = settings
        self._artifacts = ArtifactRepository(session)
        self._stage_runs = StageRunRepository(session)
        self._tasks = TaskService(session)
        self._validator = DocumentValidator(
            max_upload_bytes=settings.max_upload_bytes,
            max_archive_entries=settings.max_archive_entries,
            max_archive_uncompressed_bytes=settings.max_archive_uncompressed_bytes,
            max_image_pixels=settings.max_image_pixels,
        )
        self._parsers = DocumentParserRegistry(
            ocr_provider,
            max_chunk_chars=settings.document_chunk_chars,
            overlap_chars=settings.document_chunk_overlap_chars,
        )

    async def _existing_bundle(self, task_id: str) -> ArtifactModel | None:
        artifacts = await self._artifacts.list_for_task(task_id)
        return next(
            (
                artifact
                for artifact in reversed(artifacts)
                if artifact.kind == ArtifactKind.PARSED_DOCUMENT.value
            ),
            None,
        )

    async def _materialize_source(
        self,
        artifact: ArtifactModel,
        directory: Path,
    ) -> Path:
        metadata = artifact.metadata_json
        filename = str(metadata.get("filename") or f"{artifact.id}.bin")
        extension = Path(filename).suffix.lower()
        destination = directory / f"{artifact.id}{extension}"
        await self._artifact_store.copy_to_file(
            artifact.storage_uri,
            destination,
        )
        return destination

    async def process(self, task_id: str) -> ArtifactModel | None:
        task = await self._tasks.get_task(task_id)
        current_status = TaskStatus(task.status)
        if current_status == TaskStatus.BRIEFING:
            return await self._existing_bundle(task_id)
        if current_status not in {TaskStatus.UPLOADED, TaskStatus.PARSING}:
            raise InvalidStateTransition(
                current_status.value,
                TaskStatus.PARSING.value,
            )

        if current_status == TaskStatus.UPLOADED:
            await self._tasks.transition(
                task_id,
                TaskStatus.PARSING,
                event_type="document.parsing.started",
            )

        stage_run = await self._stage_runs.start(
            task_id=task_id,
            stage=TaskStatus.PARSING.value,
        )
        await self._session.commit()

        try:
            artifacts = await self._artifacts.list_for_task(task_id)
            source_artifacts = [
                artifact
                for artifact in artifacts
                if artifact.kind == ArtifactKind.SOURCE_DOCUMENT.value
            ]
            if not source_artifacts:
                raise InvalidDocument("Task does not contain source documents.")

            sources: list[DocumentSource] = []
            chunks = []
            tables = []
            images = []
            warnings: list[str] = []

            with TemporaryDirectory(
                dir=self._settings.upload_temp_root
            ) as temporary_directory:
                directory = Path(temporary_directory)
                for source_artifact in source_artifacts:
                    source_path = await self._materialize_source(
                        source_artifact,
                        directory,
                    )
                    metadata = source_artifact.metadata_json
                    filename = str(metadata.get("filename") or source_path.name)
                    declared_mime = str(metadata.get("declared_mime") or "")
                    validated = self._validator.validate(
                        path=source_path,
                        original_filename=filename,
                        declared_mime=declared_mime,
                    )
                    parsed = await self._parsers.parse(
                        validated,
                        source_artifact_id=source_artifact.id,
                    )
                    sources.append(
                        DocumentSource(
                            artifact_id=source_artifact.id,
                            filename=filename,
                            mime_type=validated.mime_type,
                            sha256=validated.sha256,
                            size_bytes=validated.size_bytes,
                            page_count=parsed.page_count,
                        )
                    )
                    chunks.extend(parsed.chunks)
                    tables.extend(parsed.tables)
                    images.extend(parsed.images)
                    warnings.extend(
                        f"{filename}: {warning}" for warning in parsed.warnings
                    )

                    await self._session.refresh(task)
                    if TaskStatus(task.status) == TaskStatus.CANCELLED:
                        await self._stage_runs.cancel(stage_run)
                        await self._session.commit()
                        return None

                bundle = DocumentBundle(
                    task_id=task_id,
                    sources=sources,
                    chunks=chunks,
                    tables=tables,
                    images=images,
                    warnings=warnings,
                )
                payload = bundle.model_dump_json(indent=2).encode()
                digest = sha256(payload).hexdigest()
                bundle_path = directory / "document-bundle.json"
                async with aiofiles.open(bundle_path, "wb") as output:
                    await output.write(payload)

                existing = await self._artifacts.get_by_hash(
                    task_id=task_id,
                    kind=ArtifactKind.PARSED_DOCUMENT,
                    sha256=digest,
                )
                if existing is None:
                    stored = await self._artifact_store.put_file(
                        task_id=task_id,
                        relative_path=(
                            f"parsed/{digest}/document-bundle.json"
                        ),
                        source_path=bundle_path,
                        mime_type="application/json",
                    )
                    existing = await self._artifacts.create(
                        task_id=task_id,
                        kind=ArtifactKind.PARSED_DOCUMENT,
                        stored=stored,
                        metadata={
                            "schema_version": bundle.schema_version,
                            "source_artifact_ids": [
                                source.artifact_id for source in sources
                            ],
                            "content_trust": "untrusted",
                        },
                        quality_status=QualityStatus.APPROVED,
                    )

            await self._stage_runs.complete(
                stage_run,
                output_artifact_ids=[existing.id],
            )
            await self._session.commit()
            await self._tasks.transition(
                task_id,
                TaskStatus.BRIEFING,
                event_type="document.parsed",
                payload={"artifact_id": existing.id},
            )
            return existing
        except Exception as error:
            error_code = (
                error.code
                if isinstance(error, DomainError)
                else "document_processing_failed"
            )
            await self._stage_runs.fail(stage_run, error_code)
            await self._session.commit()
            await self._tasks.transition(
                task_id,
                TaskStatus.FAILED,
                event_type="document.parsing.failed",
                payload={"code": error_code},
            )
            if isinstance(error, DomainError):
                raise
            raise DocumentProcessingFailed() from error
