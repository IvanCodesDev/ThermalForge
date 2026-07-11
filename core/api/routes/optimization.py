"""模型优化反馈闭环 API 路由。"""
from __future__ import annotations

from typing import Annotated, Callable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from core.config import Settings, get_settings
from core.models.optimization import (
    AcceptOptimizationRequest,
    SubmitOptimizationFeedbackRequest,
)
from core.providers.openai_models import OpenAIModelsClient
from core.services.agent_pipeline import (
    PipelineConflictError,
    PipelineGateError,
    PipelineNotFoundError,
)
from core.services.optimization_loop import OptimizationLoopService

router = APIRouter(prefix="/api/v1/agent-pipelines", tags=["optimization-loop"])
development_router = APIRouter(
    prefix="/api/v1/agent-pipelines", tags=["optimization-loop-development"]
)


def get_optimization_service(
    settings: Settings = Depends(get_settings),
) -> OptimizationLoopService:
    return OptimizationLoopService(settings=settings)


OptimizationServiceDep = Annotated[
    OptimizationLoopService, Depends(get_optimization_service)
]


def _call(operation: Callable[[], object]) -> object:
    try:
        return operation()
    except PipelineNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (PipelineConflictError, PipelineGateError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{pipeline_id}/optimization/enter")
def enter_optimization_loop(
    pipeline_id: UUID,
    service: OptimizationServiceDep,
):
    """从 HYPER3D_DONE / GEOMETRY_READY 进入优化审核状态。"""
    return _call(lambda: service.enter_optimization_loop(pipeline_id))


@router.post("/{pipeline_id}/optimization/feedback")
async def submit_feedback(
    pipeline_id: UUID,
    body: SubmitOptimizationFeedbackRequest,
    service: OptimizationServiceDep,
):
    """提交用户反馈，触发 LLM 解析生成优化计划。"""
    try:
        return await service.submit_feedback(pipeline_id, body)
    except (PipelineConflictError, PipelineGateError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PipelineNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{pipeline_id}/optimization/compile")
def compile_solidworks(
    pipeline_id: UUID,
    service: OptimizationServiceDep,
):
    """编译 SolidWorks 优化执行契约。"""
    return _call(lambda: service.compile_solidworks(pipeline_id))


@development_router.post("/{pipeline_id}/optimization/execute")
def execute_solidworks(
    pipeline_id: UUID,
    service: OptimizationServiceDep,
):
    """执行 SolidWorks 优化（开发模式端点）。"""
    return _call(lambda: service.execute_solidworks(pipeline_id))


@router.post("/{pipeline_id}/optimization/accept")
def accept_optimization(
    pipeline_id: UUID,
    body: AcceptOptimizationRequest,
    service: OptimizationServiceDep,
):
    """用户接受或拒绝优化结果。"""
    return _call(lambda: service.accept_optimization(
        pipeline_id, accepted=body.accepted, reviewed_by=body.reviewed_by
    ))


@router.get("/{pipeline_id}/optimization/status")
def get_optimization_status(
    pipeline_id: UUID,
    service: OptimizationServiceDep,
):
    """查询优化闭环状态。"""
    from core.services.agent_pipeline import AgentPipelineRuntime
    runtime = AgentPipelineRuntime()
    try:
        pipeline = runtime.get(pipeline_id)
    except PipelineNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "pipeline_id": str(pipeline.id),
        "state": pipeline.state,
        "current_iteration": pipeline.current_optimization_iteration,
        "total_iterations": len(pipeline.optimization_iterations),
        "solidworks_available": service.adapter.available,
        "iterations": pipeline.optimization_iterations,
    }


@router.get("/{pipeline_id}/optimization/preflight")
def solidworks_preflight(
    pipeline_id: UUID,
    service: OptimizationServiceDep,
):
    """运行 SolidWorks 预检。"""
    return service.adapter.preflight()
