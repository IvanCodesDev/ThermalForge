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


@router.get("/motor-type/{motor_type}",
             summary="按电机类型检索",
             description="在全局知识库（data/knowledge.db）中按 motor_type 检索默认电机条目（如 BLDC），返回结构化条目列表。",
             response_description="命中数量与条目列表",
             responses={200: {"description": "检索成功", "content": {"application/json": {"example": {"count": 1, "results": [{"entry_id": "kb-bldc-default", "motor_type": "BLDC", "rated_power_w": 50.0}]}}}}})
def get_by_motor_type(motor_type: str) -> dict:
    return _payload(get_library().search_by_motor_type(motor_type))


@router.get("/material/{name}",
             summary="按材质检索",
             description="在知识库中按材质名（如 al/steel）检索默认材质条目，返回兼容 MaterialProperties 的字段。",
             response_description="命中数量与条目列表",
             responses={200: {"description": "检索成功", "content": {"application/json": {"example": {"count": 1, "results": [{"material_id": "al", "name": "Aluminum", "density_kg_m3": 2700}]}}}}})
def get_by_material(name: str) -> dict:
    return _payload(get_library().search_by_material(name))


@router.get("/keyword/{text}",
             summary="按关键字检索",
             description="在知识库中按关键字（如 aluminum、无刷）检索文档/条目，用于通用数据快速调用。",
             response_description="命中数量与条目列表",
             responses={200: {"description": "检索成功", "content": {"application/json": {"example": {"count": 0, "results": []}}}}})
def get_by_keyword(text: str) -> dict:
    return _payload(get_library().search_by_keyword(text))
