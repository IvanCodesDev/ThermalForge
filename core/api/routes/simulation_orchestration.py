"""仿真编排 API。"""
from __future__ import annotations

from typing import Annotated, Any, Callable

from fastapi import APIRouter, Depends, HTTPException

from core.api.routes.engineering_state import get_engineering_state_service
from core.models.engineering_state import Artifact
from core.models.simulation_contract import (
    CompileSimulationHandoffRequest,
    RegisterSpaceClaimArtifactsRequest,
    ResultAcceptance,
    SimulationHandoffContract,
    SimulationResultContract,
)
from core.services.engineering_state import EngineeringStateConflictError, EngineeringStateNotFoundError
from core.services.simulation_contract import SimulationContractError
from core.services.simulation_orchestration import SimulationHandoffNotFoundError, SimulationOrchestrationService

router = APIRouter(prefix="/api/v1/simulation-handoffs", tags=["simulation-orchestration"])
development_router = APIRouter(prefix="/api/v1/simulation-handoffs", tags=["simulation-development"])
_services: dict[int, SimulationOrchestrationService] = {}


def get_simulation_orchestration_service() -> SimulationOrchestrationService:
    engineering = get_engineering_state_service()
    return _services.setdefault(id(engineering), SimulationOrchestrationService(engineering))


ServiceDep = Annotated[SimulationOrchestrationService, Depends(get_simulation_orchestration_service)]


def _call(operation: Callable[[], Any]) -> Any:
    try:
        return operation()
    except (EngineeringStateNotFoundError, SimulationHandoffNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (EngineeringStateConflictError, SimulationContractError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/projects/{project_id}", status_code=201,
             summary="编译仿真交接契约",
             description="将「已批准且关键值全 confirmed」的 EngineeringState 编译为 SimulationHandoffContract，"
             "返回 handoff_id 与契约对象。前置条件不满足（未 approved/含 unresolved/几何非 MANUFACTURING_CAD）时返回 409。",
             response_description="handoff_id 与编译出的契约",
             responses={201: {"description": "编译成功", "content": {"application/json": {"example": {"handoff_id": "ho_001", "contract": {"schema": "thermalforge.simulation_handoff", "version": "1.0.0"}}}}}, 404: {"description": "项目不存在"}, 409: {"description": "审批/编译条件不满足"}})
def compile_handoff(project_id: str, body: CompileSimulationHandoffRequest, service: ServiceDep) -> dict[str, Any]:
    handoff_id, contract = _call(lambda: service.compile(project_id, body))
    return {"handoff_id": handoff_id, "contract": contract.model_dump(mode="json")}


@router.get("/{handoff_id}", response_model=SimulationHandoffContract,
             summary="读取仿真交接契约",
             description="按 handoff_id 返回 SimulationHandoffContract 详情。",
             response_description="SimulationHandoffContract",
             responses={404: {"description": "交接契约不存在"}})
def get_handoff(handoff_id: str, service: ServiceDep) -> SimulationHandoffContract:
    return _call(lambda: service.get(handoff_id))


@development_router.post("/{handoff_id}/spaceclaim-artifacts", response_model=list[Artifact], status_code=201,
                         summary="登记 SpaceClaim 几何产物（开发）",
                         description="把 SpaceClaim 生成的几何 Artifact 列表挂到交接契约上，闭合几何→仿真链路。开发模式端点。",
                         response_description="登记的 Artifact 列表",
                         responses={201: {"description": "登记成功"}, 404: {"description": "交接契约不存在"}, 409: {"description": "版本冲突"}})
def register_spaceclaim_artifacts(handoff_id: str, body: RegisterSpaceClaimArtifactsRequest, service: ServiceDep) -> list[Artifact]:
    artifacts = [Artifact.model_validate(item) for item in body.artifacts]
    return _call(lambda: service.register_spaceclaim_artifacts(handoff_id, artifacts))


@development_router.post("/{handoff_id}/result", response_model=ResultAcceptance, status_code=201,
                         summary="登记仿真结果（开发）",
                         description="回灌真实 Fluent/Mechanical 仿真结果，做「先身份校验→原始登记→验收」并支持 review_required 路由。开发模式端点。",
                         response_description="结果验收结论 ResultAcceptance",
                         responses={201: {"description": "登记成功"}, 404: {"description": "交接契约不存在"}, 409: {"description": "契约/结果冲突"}})
def register_result(handoff_id: str, body: SimulationResultContract, service: ServiceDep) -> ResultAcceptance:
    return _call(lambda: service.register_result(handoff_id, body))


@router.get("/{handoff_id}/validation-summary",
             summary="仿真验收摘要",
             description="返回该交接契约的验收摘要（已登记结果、是否超阈值、是否进入 review_required）。",
             response_description="验收摘要 dict",
             responses={404: {"description": "交接契约不存在"}})
def validation_summary(handoff_id: str, service: ServiceDep) -> dict[str, object]:
    return _call(lambda: service.summary(handoff_id))
