from typing import Any, cast

from arq.connections import RedisSettings

from app.config import Settings, get_settings
from app.db import Database
from app.documents.ocr import OcrProvider, RapidOcrProvider
from app.imaging.base import ImageGenerationProvider
from app.imaging.factory import build_image_provider
from app.llm.base import LLMProvider
from app.llm.factory import build_llm_provider
from app.services.artifacts.base import ArtifactStore
from app.services.artifacts.factory import build_artifact_store
from app.services.pipeline import PipelineRunner


async def startup(context: dict[str, Any]) -> None:
    settings = get_settings()
    database = Database(settings.database_url)
    if settings.auto_create_schema:
        await database.initialize()
    else:
        await database.ping()
    settings.upload_temp_root.mkdir(parents=True, exist_ok=True)
    context["database"] = database
    context["settings"] = settings
    context["artifact_store"] = build_artifact_store(settings)
    context["ocr_provider"] = RapidOcrProvider()
    context["llm_provider"] = build_llm_provider(settings)
    context["image_provider"] = build_image_provider(settings)
    context["pipeline_runner"] = PipelineRunner(
        database=database,
        settings=settings,
        artifact_store=cast(ArtifactStore, context["artifact_store"]),
        ocr_provider=cast(OcrProvider, context["ocr_provider"]),
        llm_provider=cast(LLMProvider, context["llm_provider"]),
        image_provider=cast(ImageGenerationProvider, context["image_provider"]),
    )


async def shutdown(context: dict[str, Any]) -> None:
    database = cast(Database, context["database"])
    await database.dispose()


async def run_pipeline(context: dict[str, Any], task_id: str) -> None:
    runner = context.get("pipeline_runner")
    if runner is None:
        settings = cast(Settings | None, context.get("settings"))
        image_provider = cast(
            ImageGenerationProvider | None,
            context.get("image_provider"),
        )
        if image_provider is None and settings is not None:
            image_provider = build_image_provider(settings)
        runner = PipelineRunner(
            database=cast(Database, context["database"]),
            settings=settings,
            artifact_store=cast(ArtifactStore | None, context.get("artifact_store")),
            ocr_provider=cast(OcrProvider | None, context.get("ocr_provider")),
            llm_provider=cast(LLMProvider | None, context.get("llm_provider")),
            image_provider=image_provider,
        )
    await cast(PipelineRunner, runner).run(task_id)


class WorkerSettings:
    functions = [run_pipeline]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_jobs = 4
    job_timeout = 900
    max_tries = 3
