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


@router.put("/{project_id}/state", response_model=EngineeringState)
def put_state(project_id: str, body: PutEngineeringStateRequest, service: ServiceDep) -> EngineeringState:
    if body.state.project_id != project_id:
        raise HTTPException(status_code=422, detail="路径 project_id 与 state.project_id 不一致")
    return _call(lambda: service.put(body.state, expected_revision=body.expected_revision))


@router.get("/{project_id}/state", response_model=EngineeringState)
def get_state(
    project_id: str,
    service: ServiceDep,
    revision: int | None = Query(default=None, ge=1),
) -> EngineeringState:
    return _call(lambda: service.get(project_id, revision))


@router.post("/{project_id}/confirm", response_model=EngineeringState)
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


@router.post("/{project_id}/artifacts", response_model=Artifact, status_code=201)
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


@router.get("/{project_id}/artifacts", response_model=ArtifactRegistry)
def list_artifacts(project_id: str, service: ServiceDep) -> ArtifactRegistry:
    return _call(lambda: service.artifacts(project_id))


@router.get("/{project_id}/artifacts/{artifact_id}/lineage", response_model=ArtifactLineage)
def get_artifact_lineage(project_id: str, artifact_id: str, service: ServiceDep) -> ArtifactLineage:
    return _call(lambda: service.lineage(project_id, artifact_id))


@router.get("/{project_id}/artifacts/{artifact_id}", response_model=Artifact)
def get_artifact(project_id: str, artifact_id: str, service: ServiceDep) -> Artifact:
    return _call(lambda: service.get_artifact(project_id, artifact_id))
