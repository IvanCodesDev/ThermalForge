from app.config import Settings
from app.db import Database
from app.documents.ocr import OcrProvider
from app.domain.enums import TaskStatus
from app.imaging.base import ImageGenerationProvider
from app.llm.base import LLMProvider
from app.services.artifacts.base import ArtifactStore
from app.services.document_processing import DocumentProcessingService
from app.services.engineering_brief import EngineeringBriefService
from app.services.image_generation import ImageGenerationService
from app.services.model_completion import ModelCompletionService
from app.services.task_execution import TaskExecutionService
from app.services.tasks import TaskService
from app.services.thermal_analysis import ThermalAnalysisService


class PipelineRunner:
    def __init__(
        self,
        *,
        database: Database,
        settings: Settings | None = None,
        artifact_store: ArtifactStore | None = None,
        ocr_provider: OcrProvider | None = None,
        llm_provider: LLMProvider | None = None,
        image_provider: ImageGenerationProvider | None = None,
    ) -> None:
        self._database = database
        self._settings = settings
        self._artifact_store = artifact_store
        self._ocr_provider = ocr_provider
        self._llm_provider = llm_provider
        self._image_provider = image_provider

    async def run(self, task_id: str) -> None:
        async with self._database.session() as session:
            task = await TaskService(session).get_task(task_id)
            status = TaskStatus(task.status)
            if status == TaskStatus.CREATED:
                await TaskExecutionService(session).run_bootstrap(task_id)
                return

            if status in {TaskStatus.UPLOADED, TaskStatus.PARSING}:
                if (
                    self._artifact_store is None
                    or self._ocr_provider is None
                    or self._settings is None
                ):
                    return
                await DocumentProcessingService(
                    session=session,
                    artifact_store=self._artifact_store,
                    ocr_provider=self._ocr_provider,
                    settings=self._settings,
                ).process(task_id)
                task = await TaskService(session).get_task(task_id)
                status = TaskStatus(task.status)

            if status == TaskStatus.BRIEFING:
                if (
                    self._artifact_store is None
                    or self._llm_provider is None
                    or self._settings is None
                ):
                    return
                await EngineeringBriefService(
                    session=session,
                    artifact_store=self._artifact_store,
                    llm_provider=self._llm_provider,
                    settings=self._settings,
                ).generate(task_id)
                task = await TaskService(session).get_task(task_id)
                status = TaskStatus(task.status)

            if status == TaskStatus.THERMAL_ANALYSIS:
                if (
                    self._artifact_store is None
                    or self._llm_provider is None
                    or self._settings is None
                ):
                    return
                await ThermalAnalysisService(
                    session=session,
                    artifact_store=self._artifact_store,
                    llm_provider=self._llm_provider,
                    settings=self._settings,
                ).generate(task_id)
                task = await TaskService(session).get_task(task_id)
                status = TaskStatus(task.status)

            if status in {
                TaskStatus.CONCEPT_IMAGING,
                TaskStatus.MULTIVIEW_IMAGING,
                TaskStatus.MULTIVIEW_REVIEW,
            }:
                if self._artifact_store is None or self._image_provider is None:
                    return
                await ImageGenerationService(
                    session=session,
                    artifact_store=self._artifact_store,
                    image_provider=self._image_provider,
                ).generate(task_id)
                task = await TaskService(session).get_task(task_id)
                status = TaskStatus(task.status)

            if status in {TaskStatus.MODELING, TaskStatus.MODEL_REVIEW}:
                if self._artifact_store is None or self._settings is None:
                    return
                await ModelCompletionService(
                    session=session,
                    artifact_store=self._artifact_store,
                    settings=self._settings,
                ).complete(task_id)
