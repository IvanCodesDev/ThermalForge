"""版本化 EngineeringState 与 ArtifactRegistry API。"""
from __future__ import annotations

from typing import Annotated, Callable

from fastapi import APIRouter, Depends, HTTPException, Query

from core.models.engineering_state import (
    Artifact,
    ArtifactLineage,
    ArtifactRegistry,
    ConfirmEngineeringStateRequest,
    EngineeringState,
    PutEngineeringStateRequest,
    RegisterArtifactRequest,
)
from core.services.engineering_state import (
    EngineeringStateConflictError,
    EngineeringStateGateError,
    EngineeringStateNotFoundError,
    EngineeringStateService,
)

router = APIRouter(prefix="/api/v1/engineering-projects", tags=["engineering-state"])
_service = EngineeringStateService()


def get_engineering_state_service() -> EngineeringStateService:
    return _service


ServiceDep = Annotated[EngineeringStateService, Depends(get_engineering_state_service)]


def _call(operation: Callable[[], object]) -> object:
    try:
        return operation()
    except EngineeringStateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (EngineeringStateConflictError, EngineeringStateGateError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.put("/{project_id}/state", response_model=EngineeringState,
             summary="写入工程状态",
             description="版本化写入 EngineeringState（唯一事实源）。expected_revision 用于乐观锁，冲突返回 409。路径 project_id 必须与 body 中一致。",
             response_description="写入后的 EngineeringState",
             responses={422: {"description": "路径与 body 的 project_id 不一致"}, 409: {"description": "版本冲突"}, 404: {"description": "项目不存在"}})
def put_state(project_id: str, body: PutEngineeringStateRequest, service: ServiceDep) -> EngineeringState:
    if body.state.project_id != project_id:
        raise HTTPException(status_code=422, detail="路径 project_id 与 state.project_id 不一致")
    return _call(lambda: service.put(body.state, expected_revision=body.expected_revision))


@router.get("/{project_id}/state", response_model=EngineeringState,
             summary="读取工程状态",
             description="按 project_id（可选 revision）读取 EngineeringState。省略 revision 时返回最新版。",
             response_description="EngineeringState",
             responses={404: {"description": "项目或指定版本不存在"}})
def get_state(
    project_id: str,
    service: ServiceDep,
    revision: int | None = Query(default=None, ge=1),
) -> EngineeringState:
    return _call(lambda: service.get(project_id, revision))


@router.post("/{project_id}/confirm", response_model=EngineeringState,
             summary="确认工程状态",
             description="对指定版本的 EngineeringState 做人工确认（审批门），记录确认人、主题与证据，推进 approved 状态。",
             response_description="确认后的 EngineeringState",
             responses={404: {"description": "项目不存在"}, 409: {"description": "版本冲突或阶段门错误"}})
def confirm_state(
    project_id: str,
    body: ConfirmEngineeringStateRequest,
    service: ServiceDep,
) -> EngineeringState:
    return _call(lambda: service.confirm(
        project_id,
        expected_revision=body.expected_revision,
        reviewed_by=body.reviewed_by,
        subject=body.subject,
        evidence=body.evidence,
    ))


@router.post("/{project_id}/artifacts", response_model=Artifact, status_code=201,
             summary="登记 Artifact",
             description="登记一个不可变 Artifact（如 STEP/SCDOC/JSON），返回带血缘的 Artifact 对象。开发期用于把几何/仿真产物挂到状态上。",
             response_description="新建的 Artifact",
             responses={201: {"description": "登记成功"}, 404: {"description": "项目不存在"}, 409: {"description": "版本冲突"}})
def register_artifact(
    project_id: str,
    body: RegisterArtifactRequest,
    service: ServiceDep,
) -> Artifact:
    return _call(lambda: service.register_artifact(
        project_id,
        body.artifact,
        expected_revision=body.expected_revision,
    ))


@router.get("/{project_id}/artifacts", response_model=ArtifactRegistry,
             summary="列出 Artifact 注册表",
             description="返回该项目的全部 Artifact 注册表（含 lineage 索引）。",
             response_description="ArtifactRegistry",
             responses={404: {"description": "项目不存在"}})
def list_artifacts(project_id: str, service: ServiceDep) -> ArtifactRegistry:
    return _call(lambda: service.artifacts(project_id))


@router.get("/{project_id}/artifacts/{artifact_id}/lineage", response_model=ArtifactLineage,
             summary="查询 Artifact 血缘",
             description="返回指定 Artifact 的来源与下游血缘关系（不可变 lineage）。",
             response_description="ArtifactLineage",
             responses={404: {"description": "项目或 Artifact 不存在"}})
def get_artifact_lineage(project_id: str, artifact_id: str, service: ServiceDep) -> ArtifactLineage:
    return _call(lambda: service.lineage(project_id, artifact_id))


@router.get("/{project_id}/artifacts/{artifact_id}", response_model=Artifact,
             summary="读取单个 Artifact",
             description="按 artifact_id 返回单个 Artifact 详情。",
             response_description="Artifact",
             responses={404: {"description": "项目或 Artifact 不存在"}})
def get_artifact(project_id: str, artifact_id: str, service: ServiceDep) -> Artifact:
    return _call(lambda: service.get_artifact(project_id, artifact_id))
