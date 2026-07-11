"""框架无关的 Agent 工作台数据契约。"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, field_validator


class WorkbenchState(StrEnum):
    DRAFT = "draft"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    CONFIRMED = "confirmed"
    EVALUATING = "evaluating"
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"


class EngineeringBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    source_text: str = Field(min_length=1)
    device_type: str = "关节电机"
    dimensions: dict[str, PositiveFloat] = Field(
        default_factory=lambda: {"length_mm": 60.0, "width_mm": 60.0, "height_mm": 40.0}
    )
    power_w: PositiveFloat = 28.0
    max_temp_c: PositiveFloat = 80.0
    material: str = "铝6061"
    has_fan: bool = False
    max_weight_g: PositiveFloat = 60.0
    manufacturing: str = "3D打印"
    ambient_temp_c: float = 25.0
    missing_fields: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    state: WorkbenchState = WorkbenchState.AWAITING_CONFIRMATION
    revision: int = Field(default=1, ge=1)

    @field_validator("source_text")
    @classmethod
    def source_text_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("source_text 不能为空")
        return value


class BriefExtractionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=10_000)


class BriefConfirmationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    accepted: bool
    confirmed_by: str = Field(min_length=1, max_length=200)
    expected_revision: int = Field(ge=1)

    @field_validator("confirmed_by")
    @classmethod
    def confirmed_by_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("confirmed_by 不能为空")
        return value


class BriefConfirmation(BaseModel):
    brief_id: UUID
    accepted: bool
    confirmed_by: str
    confirmed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    revision: int


class EvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    brief_id: UUID


class EvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brief_id: UUID
    state: Literal[WorkbenchState.COMPLETED] = WorkbenchState.COMPLETED
    fidelity: Literal["screening"] = "screening"
    backend: Literal["lumped_estimator"] = "lumped_estimator"
    not_cfd: Literal[True] = True
    recommended_parameters: dict[str, Any]
    svg: str
    geometry: dict[str, float]
    metrics: dict[str, Any]
    limitations: list[str]


class WorkbenchCapabilities(BaseModel):
    runtime: Literal["local"] = "local"
    adapter_boundary: str = "AgentWorkbenchAdapter"
    external_agent_sdk_connected: Literal[False] = False
    brief_extraction: Literal["deterministic_keywords"] = "deterministic_keywords"
    requires_human_confirmation: Literal[True] = True
    evaluation_fidelity: Literal["screening"] = "screening"
    evaluation_backend: Literal["lumped_estimator"] = "lumped_estimator"
    not_cfd: Literal[True] = True
    supported_languages: list[str] = Field(default_factory=lambda: ["zh-CN", "en"])
    supported_structure_types: list[str] = Field(default_factory=lambda: ["leaf_vein", "channel", "flat"])
