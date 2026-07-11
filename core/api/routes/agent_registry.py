"""Agent 治理元数据与执行审计查询 API。"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Query
from core.agents.definitions import PROMPTS, SKILLS, TOOLS, build_agent_registry
from core.config import get_settings

router = APIRouter(prefix="/api/v1", tags=["agent-governance"])
development_router = APIRouter(prefix="/api/v1", tags=["agent-governance-development"])
_registry = build_agent_registry(get_settings())

@router.get("/agent-definitions")
def definitions() -> dict[str, object]:
    agents = list(_registry._items.values())
    return {
        "definitions": [item.model_dump(mode="json") for item in agents],
        "prompts": [{"id": p.id, "version": p.version, "sha256": p.sha256} for p in PROMPTS],
        "skills": [s.model_dump(mode="json") for s in SKILLS],
        "tools": [t.model_dump(mode="json") for t in TOOLS],
    }

@development_router.get("/agent-executions/{execution_id}")
def execution(execution_id: str) -> dict[str, object]:
    raise HTTPException(status_code=404, detail=f"execution {execution_id} 不存在")

@development_router.get("/agent-executions")
def executions(project_id: str | None = Query(default=None), revision: int | None = Query(default=None)) -> list[object]:
    return []
