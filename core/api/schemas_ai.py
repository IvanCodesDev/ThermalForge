"""外部模型 API 请求契约。"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class GPT55ResponseIn(BaseModel):
    input: str | list[dict[str, Any]]
    instructions: str | None = None
    model: str | None = None
    previous_response_id: str | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_output_tokens: int | None = Field(default=None, ge=1)
    metadata: dict[str, str] | None = None


class GPTImage2GenerateIn(BaseModel):
    prompt: str = Field(min_length=1)
    model: str | None = None
    n: int = Field(default=1, ge=1, le=10)
    size: str = "1024x1024"
    quality: Literal["auto", "low", "medium", "high"] = "auto"
    output_format: Literal["png", "jpeg", "webp"] = "png"
    background: Literal["auto", "opaque"] = "auto"
    moderation: Literal["auto", "low"] = "auto"


class Hyper3DImageIn(BaseModel):
    filename: str = "reference.png"
    content_base64: str
    content_type: str = "image/png"


class Hyper3DRodinOptions(BaseModel):
    """Rodin Gen-2 官方生成参数的显式契约。"""

    tier: Literal["Gen-2"] = "Gen-2"
    use_original_alpha: bool | None = None
    seed: int | None = Field(default=None, ge=0)
    geometry_file_format: Literal["glb", "usdz", "fbx", "obj", "stl"] = "glb"
    material: Literal["PBR", "Shaded", "All", "None"] = "PBR"
    quality: Literal["medium", "high"] | None = None
    quality_override: int | None = Field(default=None, ge=1)
    ta_pose: bool | None = Field(default=None, alias="TAPose")
    bbox_condition: list[float] | None = Field(default=None, min_length=3, max_length=3)
    mesh_mode: Literal["Quad", "Raw"] | None = None
    addons: list[str] | None = None
    preview_render: bool | None = None
    hd_texture: bool | None = None


class Hyper3DSubmitIn(BaseModel):
    prompt: str | None = None
    images: list[Hyper3DImageIn] = Field(default_factory=list, max_length=5)
    options: Hyper3DRodinOptions = Field(default_factory=Hyper3DRodinOptions)

    @model_validator(mode="after")
    def validate_source(self):
        if not self.prompt and not self.images:
            raise ValueError("prompt 与 images 至少提供一项")
        return self


class Hyper3DModelIn(BaseModel):
    filename: str = "model.glb"
    content_base64: str
    content_type: str = "model/gltf-binary"


class Hyper3DBangIn(BaseModel):
    """Bang 分件请求；asset_id 与上传模型二选一。"""

    asset_id: str | None = None
    model: Hyper3DModelIn | None = None
    image: Hyper3DImageIn | None = None
    prompt: str | None = None
    strength: int = Field(default=5, ge=2, le=12)
    geometry_file_format: Literal["glb", "usdz", "fbx", "obj", "stl"] = "glb"
    material: Literal["PBR", "Shaded", "All", "None"] = "PBR"
    resolution: Literal["Basic", "High"] = "Basic"

    @model_validator(mode="after")
    def validate_source(self):
        if bool(self.asset_id) == bool(self.model):
            raise ValueError("asset_id 与 model 必须且只能提供一项")
        if self.asset_id and (self.image or self.prompt):
            raise ValueError("asset_id 模式不接受 image 或 prompt；官方接口会忽略这些字段")
        if self.image and not self.model:
            raise ValueError("image 只能与自定义 model 配对使用")
        return self


class Hyper3DStatusIn(BaseModel):
    subscription_key: str = Field(min_length=1)


class Hyper3DDownloadIn(BaseModel):
    task_uuid: str = Field(min_length=1)
