"""Agent 治理元数据与执行审计查询 API。"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Query
from core.agents.definitions import PROMPTS, SKILLS, TOOLS, build_agent_registry
from core.config import get_settings

router = APIRouter(prefix="/api/v1", tags=["agent-governance"])
development_router = APIRouter(prefix="/api/v1", tags=["agent-governance-development"])
_registry = build_agent_registry(get_settings())

@router.get("/agent-definitions",
             summary="查询 Agent 治理元数据",
             description="返回全部 Agent 定义、Prompt（含 version 与 sha256）、Skill 与 Tool 策略的只读快照，用于治理审计与前端展示。",
             response_description="治理元数据对象",
             responses={200: {"description": "查询成功", "content": {"application/json": {"example": {"definitions": [], "prompts": [{"id": "p1", "version": "1", "sha256": "abc..."}], "skills": [], "tools": []}}}}})
def definitions() -> dict[str, object]:
    agents = list(_registry._items.values())
    return {
        "definitions": [item.model_dump(mode="json") for item in agents],
        "prompts": [{"id": p.id, "version": p.version, "sha256": p.sha256} for p in PROMPTS],
        "skills": [s.model_dump(mode="json") for s in SKILLS],
        "tools": [t.model_dump(mode="json") for t in TOOLS],
    }

@development_router.get("/agent-executions/{execution_id}",
                         summary="查询单次执行记录（开发）",
                         description="按 execution_id 查询 Agent 执行审计记录。开发模式端点（当前为占位实现）。",
                         response_description="执行记录",
                         responses={404: {"description": "执行记录不存在"}})
def execution(execution_id: str) -> dict[str, object]:
    raise HTTPException(status_code=404, detail=f"execution {execution_id} 不存在")

@development_router.get("/agent-executions",
                         summary="列出执行记录（开发）",
                         description="按 project_id / revision 过滤列出 Agent 执行审计记录。开发模式端点（当前返回空列表）。",
                         response_description="执行记录列表")
def executions(project_id: str | None = Query(default=None), revision: int | None = Query(default=None)) -> list[object]:
    return []
