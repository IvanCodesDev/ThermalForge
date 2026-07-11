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


@router.post("/projects/{project_id}", status_code=201)
def compile_handoff(project_id: str, body: CompileSimulationHandoffRequest, service: ServiceDep) -> dict[str, Any]:
    handoff_id, contract = _call(lambda: service.compile(project_id, body))
    return {"handoff_id": handoff_id, "contract": contract.model_dump(mode="json")}


@router.get("/{handoff_id}", response_model=SimulationHandoffContract)
def get_handoff(handoff_id: str, service: ServiceDep) -> SimulationHandoffContract:
    return _call(lambda: service.get(handoff_id))


@development_router.post("/{handoff_id}/spaceclaim-artifacts", response_model=list[Artifact], status_code=201)
def register_spaceclaim_artifacts(handoff_id: str, body: RegisterSpaceClaimArtifactsRequest, service: ServiceDep) -> list[Artifact]:
    artifacts = [Artifact.model_validate(item) for item in body.artifacts]
    return _call(lambda: service.register_spaceclaim_artifacts(handoff_id, artifacts))


@development_router.post("/{handoff_id}/result", response_model=ResultAcceptance, status_code=201)
def register_result(handoff_id: str, body: SimulationResultContract, service: ServiceDep) -> ResultAcceptance:
    return _call(lambda: service.register_result(handoff_id, body))


@router.get("/{handoff_id}/validation-summary")
def validation_summary(handoff_id: str, service: ServiceDep) -> dict[str, object]:
    return _call(lambda: service.summary(handoff_id))
