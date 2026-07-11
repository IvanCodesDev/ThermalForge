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


@router.post("", response_model=AgentPipeline, status_code=201,
            summary="创建 Agent 流水线",
            description="基于请求体创建一条可审计的 Agent 流水线（数据手册 → Hyper3D 资产），返回初始 Pipeline 对象。",
            response_description="新建的 AgentPipeline",
            responses={201: {"description": "创建成功", "content": {"application/json": {"example": {"id": "3f1a...", "project_id": "iki1602", "stage": "created"}}}}})
def create_pipeline(body: CreatePipelineRequest, runtime: RuntimeDep) -> AgentPipeline:
    return runtime.create(body)


@router.get("/{pipeline_id}", response_model=AgentPipeline,
            summary="获取流水线",
            description="按 pipeline_id 返回完整 Pipeline 对象（含各阶段状态与登记产物）。",
            response_description="AgentPipeline",
            responses={404: {"description": "流水线不存在"}})
def get_pipeline(pipeline_id: UUID, runtime: RuntimeDep) -> AgentPipeline:
    return _call(lambda: runtime.get(pipeline_id))


@router.get("/{pipeline_id}/status", response_model=PipelineStatus,
            summary="获取流水线状态",
            description="返回流水线的阶段状态机快照（created/extracting/specified/reviewing/...）。",
            response_description="PipelineStatus",
            responses={404: {"description": "流水线不存在"}})
def get_pipeline_status(pipeline_id: UUID, runtime: RuntimeDep) -> PipelineStatus:
    return _call(lambda: runtime.status(pipeline_id))


@router.get("/{pipeline_id}/manifest", response_model=FrontendPipelineManifest,
            summary="获取前端 Manifest",
            description="返回前端可消费的交付 Manifest（模型 URL、爆炸变换、组件、置信度与讲解）。",
            response_description="FrontendPipelineManifest",
            responses={404: {"description": "流水线不存在"}})
def get_pipeline_manifest(pipeline_id: UUID, runtime: RuntimeDep) -> FrontendPipelineManifest:
    return _call(lambda: runtime.frontend_manifest(pipeline_id))


@router.post("/{pipeline_id}/specification/extract", response_model=AgentPipeline,
             summary="抽取工程规格",
             description="调用 LLM（gpt-5.6-sol）从源文档内容抽取工程规格，并记录所用 Agent/Prompt 定义，返回更新后的流水线。",
             response_description="更新后的 AgentPipeline",
             responses={404: {"description": "流水线不存在"}, 409: {"description": "阶段门或冲突错误"}})
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


@router.post("/{pipeline_id}/specification", response_model=AgentPipeline,
            summary="提议工程规格",
            description="由上游/人工提交工程规格草案，进入待评审状态。",
            response_description="更新后的 AgentPipeline",
            responses={404: {"description": "流水线不存在"}, 409: {"description": "阶段门或冲突错误"}})
def propose_specification(pipeline_id: UUID, body: ProposeSpecificationRequest, runtime: RuntimeDep) -> AgentPipeline:
    return _call(lambda: runtime.propose_specification(pipeline_id, body.specification))


@router.post("/{pipeline_id}/specification/review", response_model=AgentPipeline,
            summary="评审工程规格",
            description="对提议的规格做接受/拒绝评审，记录评审人与期望版本。",
            response_description="更新后的 AgentPipeline",
            responses={404: {"description": "流水线不存在"}, 409: {"description": "阶段门或冲突错误"}})
def review_specification(pipeline_id: UUID, body: ReviewRequest, runtime: RuntimeDep) -> AgentPipeline:
    return _call(lambda: runtime.review_specification(
        pipeline_id,
        accepted=body.accepted,
        reviewed_by=body.reviewed_by,
        expected_revision=body.expected_revision,
    ))


@development_router.post("/{pipeline_id}/geometry", response_model=AgentPipeline,
                         summary="登记几何产物（开发）",
                         description="登记由 SpaceClaim/网格等产出的几何 Artifact 列表，进入几何阶段。开发模式端点。",
                         response_description="更新后的 AgentPipeline",
                         responses={404: {"description": "流水线不存在"}, 409: {"description": "阶段门或冲突错误"}})
def register_geometry(pipeline_id: UUID, body: RegisterGeometryRequest, runtime: RuntimeDep) -> AgentPipeline:
    return _call(lambda: runtime.register_geometry(pipeline_id, body.artifacts))


@router.post("/{pipeline_id}/hyper3d/compile", response_model=AgentPipeline,
            summary="编译 Hyper3D 请求",
            description="将评审通过的规格编译为 Hyper3D Rodin 请求（提示词 + 图像清单），进入提交准备。",
            response_description="更新后的 AgentPipeline",
            responses={404: {"description": "流水线不存在"}, 409: {"description": "阶段门或冲突错误"}})
def compile_hyper3d(pipeline_id: UUID, runtime: RuntimeDep) -> AgentPipeline:
    return _call(lambda: runtime.compile_hyper3d(pipeline_id))


@development_router.post("/{pipeline_id}/hyper3d/submitted", response_model=AgentPipeline,
                         summary="标记 Hyper3D 已提交（开发）",
                         description="记录 Hyper3D 提交的 task_uuid，进入轮询阶段。开发模式端点。",
                         response_description="更新后的 AgentPipeline",
                         responses={404: {"description": "流水线不存在"}, 409: {"description": "阶段门或冲突错误"}})
def mark_hyper3d_submitted(pipeline_id: UUID, body: SubmitHyper3DRequest, runtime: RuntimeDep) -> AgentPipeline:
    return _call(lambda: runtime.mark_hyper3d_submitted(pipeline_id, body.task_uuid))


@development_router.post("/{pipeline_id}/hyper3d/result", response_model=AgentPipeline,
                         summary="登记 Hyper3D 结果（开发）",
                         description="登记 Hyper3D 任务完成后的资产（GLB/图像及来源 Manifest）。开发模式端点。",
                         response_description="更新后的 AgentPipeline",
                         responses={404: {"description": "流水线不存在"}, 409: {"description": "阶段门或冲突错误"}})
def register_hyper3d_result(pipeline_id: UUID, body: RegisterHyper3DResultRequest, runtime: RuntimeDep) -> AgentPipeline:
    return _call(lambda: runtime.register_hyper3d_result(pipeline_id, body.task_uuid, body.artifacts))


@development_router.post("/{pipeline_id}/validation", response_model=AgentPipeline,
                         summary="提交验证报告（开发）",
                         description="提交尺寸/轴线碰撞等验证报告，进入可交付状态。开发模式端点。",
                         response_description="更新后的 AgentPipeline",
                         responses={404: {"description": "流水线不存在"}, 409: {"description": "阶段门或冲突错误"}})
def submit_validation(pipeline_id: UUID, body: ValidationReport, runtime: RuntimeDep) -> AgentPipeline:
    return _call(lambda: runtime.submit_validation(pipeline_id, body))
