"""数据手册到 Hyper3D 资产的可审计 Agent 流水线 API。"""
from __future__ import annotations

from typing import Annotated, Callable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from core.config import Settings, get_settings
from core.models.agent_pipeline import (
    AgentPipeline,
    CreatePipelineRequest,
    ExtractSpecificationRequest,
    FrontendPipelineManifest,
    PipelineStatus,
    ProposeSpecificationRequest,
    RegisterGeometryRequest,
    RegisterHyper3DResultRequest,
    ReviewRequest,
    SubmitHyper3DRequest,
    ValidationReport,
)
from core.providers.openai_models import OpenAIModelsClient
from core.services.agent_pipeline import (
    AgentPipelineRuntime,
    PipelineConflictError,
    PipelineGateError,
    PipelineNotFoundError,
    SpecificationExtractionService,
)

router = APIRouter(prefix="/api/v1/agent-pipelines", tags=["agent-pipeline"])
development_router = APIRouter(prefix="/api/v1/agent-pipelines", tags=["agent-pipeline-development"])
_runtime = AgentPipelineRuntime()


def get_agent_pipeline_runtime() -> AgentPipelineRuntime:
    return _runtime


def get_specification_extraction_service(
    settings: Settings = Depends(get_settings),
) -> SpecificationExtractionService:
    return SpecificationExtractionService(settings, OpenAIModelsClient(settings))


RuntimeDep = Annotated[AgentPipelineRuntime, Depends(get_agent_pipeline_runtime)]
ExtractionServiceDep = Annotated[
    SpecificationExtractionService,
    Depends(get_specification_extraction_service),
]


def _call(operation: Callable[[], object]) -> object:
    try:
        return operation()
    except PipelineNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (PipelineConflictError, PipelineGateError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("", response_model=AgentPipeline, status_code=201)
def create_pipeline(body: CreatePipelineRequest, runtime: RuntimeDep) -> AgentPipeline:
    return runtime.create(body)


@router.get("/{pipeline_id}", response_model=AgentPipeline)
def get_pipeline(pipeline_id: UUID, runtime: RuntimeDep) -> AgentPipeline:
    return _call(lambda: runtime.get(pipeline_id))


@router.get("/{pipeline_id}/status", response_model=PipelineStatus)
def get_pipeline_status(pipeline_id: UUID, runtime: RuntimeDep) -> PipelineStatus:
    return _call(lambda: runtime.status(pipeline_id))


@router.get("/{pipeline_id}/manifest", response_model=FrontendPipelineManifest)
def get_pipeline_manifest(pipeline_id: UUID, runtime: RuntimeDep) -> FrontendPipelineManifest:
    return _call(lambda: runtime.frontend_manifest(pipeline_id))


@router.post("/{pipeline_id}/specification/extract", response_model=AgentPipeline)
async def extract_specification(
    pipeline_id: UUID,
    body: ExtractSpecificationRequest,
    runtime: RuntimeDep,
    service: ExtractionServiceDep,
) -> AgentPipeline:
    pipeline = _call(lambda: runtime.get(pipeline_id))
    try:
        result = await service.extract(pipeline, body.source_contents)
        return runtime.record_extracted_specification(
            pipeline_id,
            result,
            agent_definition=service.agent,
            prompt_definition=service.prompt,
        )
    except (PipelineConflictError, PipelineGateError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{pipeline_id}/specification", response_model=AgentPipeline)
def propose_specification(pipeline_id: UUID, body: ProposeSpecificationRequest, runtime: RuntimeDep) -> AgentPipeline:
    return _call(lambda: runtime.propose_specification(pipeline_id, body.specification))


@router.post("/{pipeline_id}/specification/review", response_model=AgentPipeline)
def review_specification(pipeline_id: UUID, body: ReviewRequest, runtime: RuntimeDep) -> AgentPipeline:
    return _call(lambda: runtime.review_specification(
        pipeline_id,
        accepted=body.accepted,
        reviewed_by=body.reviewed_by,
        expected_revision=body.expected_revision,
    ))


@development_router.post("/{pipeline_id}/geometry", response_model=AgentPipeline)
def register_geometry(pipeline_id: UUID, body: RegisterGeometryRequest, runtime: RuntimeDep) -> AgentPipeline:
    return _call(lambda: runtime.register_geometry(pipeline_id, body.artifacts))


@router.post("/{pipeline_id}/hyper3d/compile", response_model=AgentPipeline)
def compile_hyper3d(pipeline_id: UUID, runtime: RuntimeDep) -> AgentPipeline:
    return _call(lambda: runtime.compile_hyper3d(pipeline_id))


@development_router.post("/{pipeline_id}/hyper3d/submitted", response_model=AgentPipeline)
def mark_hyper3d_submitted(pipeline_id: UUID, body: SubmitHyper3DRequest, runtime: RuntimeDep) -> AgentPipeline:
    return _call(lambda: runtime.mark_hyper3d_submitted(pipeline_id, body.task_uuid))


@development_router.post("/{pipeline_id}/hyper3d/result", response_model=AgentPipeline)
def register_hyper3d_result(pipeline_id: UUID, body: RegisterHyper3DResultRequest, runtime: RuntimeDep) -> AgentPipeline:
    return _call(lambda: runtime.register_hyper3d_result(pipeline_id, body.task_uuid, body.artifacts))


@development_router.post("/{pipeline_id}/validation", response_model=AgentPipeline)
def submit_validation(pipeline_id: UUID, body: ValidationReport, runtime: RuntimeDep) -> AgentPipeline:
    return _call(lambda: runtime.submit_validation(pipeline_id, body))
