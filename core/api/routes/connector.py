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


@router.get("/status")
def connector_status():
    return _handle(lambda: get_connector().status())


@router.post("/files/list")
def connector_files_list(body: FileListIn):
    return _handle(lambda: {"files": get_connector().list_files(body.path, body.patterns, body.limit)})


@router.post("/files/read")
def connector_files_read(body: FileReadIn):
    return _handle(lambda: {"path": body.path, "content": get_connector().read_text(body.path, body.max_chars)})


@router.post("/files/replace")
def connector_files_replace(body: FileReplaceIn):
    return _handle(lambda: get_connector().replace_text(body.path, body.old_text, body.new_text))


@router.post("/model/create")
def connector_model_create(body: ModelCreateIn):
    return _handle(lambda: get_connector().create_model(body.params, body.candidate_id, body.execute))


@router.post("/model/verify-change")
def connector_model_verify_change(body: ModelVerifyIn):
    return _handle(
        lambda: get_connector().verify_model_change(
            body.baseline_params,
            body.changed_params,
            body.execute,
        )
    )
