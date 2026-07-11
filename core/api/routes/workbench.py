"""Agent 工作台首个纵向切片 API。"""
from __future__ import annotations

from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from core.workbench.contracts import (
    BriefConfirmationRequest,
    BriefExtractionRequest,
    EngineeringBrief,
    EvaluationRequest,
    EvaluationResult,
    WorkbenchCapabilities,
)
from core.workbench.runtime import (
    ConfirmationRequiredError,
    LocalWorkbenchRuntime,
    RevisionConflictError,
    WorkbenchNotFoundError,
)
from core.workbench.state_machine import InvalidWorkbenchTransition


router = APIRouter(prefix="/api/v1/workbench", tags=["agent-workbench"])
_DATA = Path(__file__).resolve().parents[3] / "data"
_runtime = LocalWorkbenchRuntime(_DATA / "seed_library.json")


def get_workbench_runtime() -> LocalWorkbenchRuntime:
    return _runtime


RuntimeDep = Annotated[LocalWorkbenchRuntime, Depends(get_workbench_runtime)]


@router.get("/capabilities", response_model=WorkbenchCapabilities)
def capabilities(runtime: RuntimeDep) -> WorkbenchCapabilities:
    return runtime.capabilities()


@router.post("/briefs/extract", response_model=EngineeringBrief, status_code=201)
def extract_brief(body: BriefExtractionRequest, runtime: RuntimeDep) -> EngineeringBrief:
    return runtime.extract_brief(body.text)


@router.get("/briefs/{brief_id}", response_model=EngineeringBrief)
def get_brief(brief_id: UUID, runtime: RuntimeDep) -> EngineeringBrief:
    try:
        return runtime.get_brief(brief_id)
    except WorkbenchNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/briefs/{brief_id}/confirm", response_model=EngineeringBrief)
def confirm_brief(
    brief_id: UUID,
    body: BriefConfirmationRequest,
    runtime: RuntimeDep,
) -> EngineeringBrief:
    try:
        return runtime.confirm_brief(
            brief_id,
            accepted=body.accepted,
            confirmed_by=body.confirmed_by,
            expected_revision=body.expected_revision,
        )
    except WorkbenchNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RevisionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvalidWorkbenchTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/evaluations", response_model=EvaluationResult)
def create_evaluation(body: EvaluationRequest, runtime: RuntimeDep) -> EvaluationResult:
    try:
        return runtime.evaluate_brief(body.brief_id)
    except WorkbenchNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConfirmationRequiredError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvalidWorkbenchTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"workbench evaluation failed: {exc}") from exc
