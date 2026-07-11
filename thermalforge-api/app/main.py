from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    clarifications,
    documents,
    engineering,
    health,
    images,
    projects,
    tasks,
    thermal,
    viewer,
)
from app.config import Settings, get_settings
from app.db import Database
from app.documents.ocr import RapidOcrProvider
from app.domain.errors import DomainError
from app.domain.schemas import ErrorBody
from app.imaging.factory import build_image_provider
from app.llm.factory import build_llm_provider
from app.services.artifacts.factory import build_artifact_store
from app.services.pipeline import PipelineRunner
from app.services.queue import ArqTaskQueue, InProcessTaskQueue


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        database = Database(resolved_settings.database_url)
        if resolved_settings.auto_create_schema:
            await database.initialize()
        else:
            await database.ping()
        artifact_store = build_artifact_store(resolved_settings)
        ocr_provider = RapidOcrProvider()
        llm_provider = build_llm_provider(resolved_settings)
        image_provider = build_image_provider(resolved_settings)
        pipeline_runner = PipelineRunner(
            database=database,
            settings=resolved_settings,
            artifact_store=artifact_store,
            ocr_provider=ocr_provider,
            llm_provider=llm_provider,
            image_provider=image_provider,
        )
        task_queue = (
            await ArqTaskQueue.connect(resolved_settings.redis_url)
            if resolved_settings.queue_enabled
            else InProcessTaskQueue(pipeline_runner)
        )

        application.state.settings = resolved_settings
        application.state.database = database
        application.state.artifact_store = artifact_store
        application.state.ocr_provider = ocr_provider
        application.state.llm_provider = llm_provider
        application.state.image_provider = image_provider
        application.state.pipeline_runner = pipeline_runner
        application.state.task_queue = task_queue
        resolved_settings.upload_temp_root.mkdir(parents=True, exist_ok=True)

        try:
            yield
        finally:
            await task_queue.close()
            await database.dispose()

    application = FastAPI(
        title="ThermalForge API",
        version="0.1.0",
        lifespan=lifespan,
    )

    if resolved_settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=resolved_settings.cors_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Content-Type", "Idempotency-Key", "Last-Event-ID"],
        )

    @application.middleware("http")
    async def attach_trace_id(request: Request, call_next):  # type: ignore[no-untyped-def]
        trace_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.trace_id = trace_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = trace_id
        return response

    @application.exception_handler(DomainError)
    async def handle_domain_error(
        request: Request,
        error: DomainError,
    ) -> JSONResponse:
        body = ErrorBody(
            code=error.code,
            message=error.message,
            retryable=error.retryable,
            trace_id=getattr(request.state, "trace_id", None),
        )
        return JSONResponse(
            status_code=error.status_code,
            content=body.model_dump(mode="json"),
        )

    @application.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        body = ErrorBody(
            code="validation_error",
            message="Request validation failed.",
            retryable=False,
            trace_id=getattr(request.state, "trace_id", None),
        )
        return JSONResponse(
            status_code=422,
            content={
                **body.model_dump(mode="json"),
                "details": error.errors(),
            },
        )

    application.include_router(health.router)
    application.include_router(projects.router)
    application.include_router(tasks.router)
    application.include_router(documents.router)
    application.include_router(clarifications.router)
    application.include_router(engineering.router)
    application.include_router(thermal.router)
    application.include_router(images.router)
    application.include_router(viewer.router)
    application.include_router(viewer.library_router)
    return application


app = create_app()
