"""ThermalForge 项目连接器 API。"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.project_connector import ThermalForgeConnector

ROOT = Path(__file__).resolve().parents[3]
router = APIRouter(prefix="/connector", tags=["project-connector"])


class FileListIn(BaseModel):
    path: str = "."
    patterns: List[str] = Field(default=["*"])
    limit: int = Field(default=500, ge=1, le=2000)


class FileReadIn(BaseModel):
    path: str
    max_chars: int = Field(default=200_000, ge=1, le=1_000_000)


class FileReplaceIn(BaseModel):
    path: str
    old_text: str
    new_text: str


class ModelCreateIn(BaseModel):
    params: Dict[str, Any]
    candidate_id: str | None = None
    execute: bool = True


class ModelVerifyIn(BaseModel):
    baseline_params: Dict[str, Any]
    changed_params: Dict[str, Any]
    execute: bool = True


def get_connector() -> ThermalForgeConnector:
    return ThermalForgeConnector(ROOT)


def _handle(call):
    try:
        return call()
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"connector failed: {exc}") from exc


@router.get("/status",
             summary="连接器状态",
             description="返回项目连接器状态（项目根路径、可访问性等），用于本地开发辅助。",
             response_description="状态对象",
             responses={200: {"description": "成功", "content": {"application/json": {"example": {"root": "/project", "accessible": True}}}}})
def connector_status():
    return _handle(lambda: get_connector().status())


@router.post("/files/list",
             summary="列举文件",
             description="按路径与 glob 模式列举项目文件，支持 limit 上限。返回匹配的文件路径列表。",
             response_description="含 files 列表的对象",
             responses={200: {"description": "成功", "content": {"application/json": {"example": {"files": ["core/api/app.py", "README.md"]}}}}})
def connector_files_list(body: FileListIn):
    return _handle(lambda: {"files": get_connector().list_files(body.path, body.patterns, body.limit)})


@router.post("/files/read",
             summary="读取文件",
             description="读取指定文件的文本内容（受 max_chars 限制），返回路径与内容。",
             response_description="含 path 与 content 的对象",
             responses={200: {"description": "成功", "content": {"application/json": {"example": {"path": "README.md", "content": "# ThermalForge"}}}}})
def connector_files_read(body: FileReadIn):
    return _handle(lambda: {"path": body.path, "content": get_connector().read_text(body.path, body.max_chars)})


@router.post("/files/replace",
             summary="替换文本",
             description="在指定文件中将 old_text 全量替换为 new_text，返回受影响的统计。",
             response_description="替换结果对象",
             responses={200: {"description": "成功"}, 422: {"description": "参数非法（如 old_text 不存在）"}})
def connector_files_replace(body: FileReplaceIn):
    return _handle(lambda: get_connector().replace_text(body.path, body.old_text, body.new_text))


@router.post("/model/create",
             summary="创建模型",
             description="基于参数创建模型候选（调用 SpaceClaim/生成内核）。execute=false 时仅做干跑校验。",
             response_description="创建结果对象",
             responses={200: {"description": "成功"}, 422: {"description": "参数非法"}, 500: {"description": "连接器执行失败"}})
def connector_model_create(body: ModelCreateIn):
    return _handle(lambda: get_connector().create_model(body.params, body.candidate_id, body.execute))


@router.post("/model/verify-change",
             summary="校验模型变更",
             description="对比基线参数与变更参数，校验变更是否可安全应用（几何/碰撞等），execute=false 时仅校验不执行。",
             response_description="校验结果对象",
             responses={200: {"description": "成功"}, 422: {"description": "参数非法"}, 500: {"description": "连接器执行失败"}})
def connector_model_verify_change(body: ModelVerifyIn):
    return _handle(
        lambda: get_connector().verify_model_change(
            body.baseline_params,
            body.changed_params,
            body.execute,
        )
    )
