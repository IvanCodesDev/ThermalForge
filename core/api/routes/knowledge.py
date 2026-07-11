"""知识库检索路由（特性二 · F2）。

沿用项目既有 FastAPI 风格（成功 2xx，未找到 404，冲突 409）。提供三类检索：
* ``GET /api/v1/knowledge/motor-type/{motor_type}``
* ``GET /api/v1/knowledge/material/{name}``
* ``GET /api/v1/knowledge/keyword/{text}``

全部基于全局共享 ``data/knowledge.db``（``KnowledgeLibrary``）。
"""
from __future__ import annotations

from fastapi import APIRouter

from core.knowledge.library import KnowledgeLibrary

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])

_library: KnowledgeLibrary | None = None


def get_library() -> KnowledgeLibrary:
    """返回（惰性初始化的）全局知识库实例。"""
    global _library
    if _library is None:
        _library = KnowledgeLibrary()
    return _library


def _payload(results: list) -> dict:
    return {"count": len(results), "results": [r.model_dump() for r in results]}


@router.get("/motor-type/{motor_type}")
def get_by_motor_type(motor_type: str) -> dict:
    return _payload(get_library().search_by_motor_type(motor_type))


@router.get("/material/{name}")
def get_by_material(name: str) -> dict:
    return _payload(get_library().search_by_material(name))


@router.get("/keyword/{text}")
def get_by_keyword(text: str) -> dict:
    return _payload(get_library().search_by_keyword(text))
