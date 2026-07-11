from typing import Literal

from pydantic import BaseModel, Field


class TaskImageAsset(BaseModel):
    artifact_id: str
    kind: Literal["concept_image", "multiview_image"]
    view_id: str
    url: str
    mime_type: Literal["image/png"]
    sha256: str
    size_bytes: int
    provider: str | None = None
    provider_model: str | None = None


class TaskImageManifest(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    task_id: str
    images: list[TaskImageAsset] = Field(default_factory=list)
    notice: str = (
        "概念图用于方案沟通，不是 CAD、CFD、FEA 或制造验证结果。"
    )
