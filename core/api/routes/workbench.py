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


@router.get("/capabilities", response_model=WorkbenchCapabilities,
             summary="工作台能力",
             description="返回 Agent 工作台当前支持的能力清单（抽取、确认、评估等）。",
             response_description="WorkbenchCapabilities",
             responses={200: {"description": "成功"}})
def capabilities(runtime: RuntimeDep) -> WorkbenchCapabilities:
    return runtime.capabilities()


@router.post("/briefs/extract", response_model=EngineeringBrief, status_code=201,
             summary="抽取工程 Brief",
             description="从自然语言文本抽取结构化工程 Brief（设备上下文与热设计需求），创建并返回。",
             response_description="新建的 EngineeringBrief",
             responses={201: {"description": "抽取成功"}})
def extract_brief(body: BriefExtractionRequest, runtime: RuntimeDep) -> EngineeringBrief:
    return runtime.extract_brief(body.text)


@router.get("/briefs/{brief_id}", response_model=EngineeringBrief,
             summary="读取工程 Brief",
             description="按 brief_id 返回工程 Brief 详情。",
             response_description="EngineeringBrief",
             responses={404: {"description": "Brief 不存在"}})
def get_brief(brief_id: UUID, runtime: RuntimeDep) -> EngineeringBrief:
    try:
        return runtime.get_brief(brief_id)
    except WorkbenchNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/briefs/{brief_id}/confirm", response_model=EngineeringBrief,
             summary="确认工程 Brief",
             description="对 Brief 做接受/拒绝确认，记录确认人与期望版本，推进状态机。",
             response_description="确认后的 EngineeringBrief",
             responses={404: {"description": "Brief 不存在"}, 409: {"description": "版本冲突或非法状态转移"}})
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


@router.post("/evaluations", response_model=EvaluationResult,
             summary="评估工程 Brief",
             description="对指定 Brief 做热设计评估，返回评估结果与指标。需先确认 Brief。",
             response_description="EvaluationResult",
             responses={404: {"description": "Brief 不存在"}, 409: {"description": "需先确认 Brief 或非法状态转移"}, 400: {"description": "评估失败"}})
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
