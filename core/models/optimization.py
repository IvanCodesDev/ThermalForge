"""SolidWorks 模型优化反馈闭环数据契约。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class OptimizationFeedback(BaseModel):
    """用户对当前模型提交的自然语言反馈。"""
    model_config = ConfigDict(extra="forbid")

    iteration: int = Field(ge=1)
    feedback_text: str = Field(min_length=1)
    target_component_id: str | None = None
    submitted_by: str = Field(min_length=1)
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OptimizationInstruction(BaseModel):
    """LLM 解析出的单条结构化优化指令。"""
    model_config = ConfigDict(extra="forbid")

    operation_type: Literal[
        "modify_dimension",
        "add_feature",
        "remove_feature",
        "add_fillet",
        "add_chamfer",
        "thicken_wall",
        "add_hole",
        "add_cooling_fin",
        "modify_sketch",
        "change_appearance",
    ]
    target_component: str = Field(min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)
    rationale: str = Field(min_length=1)


class OptimizationPlan(BaseModel):
    """LLM Agent 输出的完整优化计划。"""
    model_config = ConfigDict(extra="forbid")

    iteration: int = Field(ge=1)
    feedback_summary: str = Field(min_length=1)
    instructions: list[OptimizationInstruction] = Field(min_length=1)
    source_artifact_id: str = Field(min_length=1)
    source_format: Literal["step", "stl", "glb"] = "step"
    assumptions: list[str] = Field(default_factory=list)
    summary: str = Field(min_length=1)


class SolidWorksOutputPlan(BaseModel):
    """SolidWorks 执行的输出配置。"""
    model_config = ConfigDict(extra="forbid")

    workspace_dir: str = Field(min_length=1)
    geometry_formats: tuple[Literal["step", "stl"], ...] = ("step", "stl")
    preview_required: bool = True
    multi_view: bool = True


class SolidWorksOptimizationContract(BaseModel):
    """SolidWorks 优化执行契约。"""
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    pipeline_id: UUID
    iteration: int = Field(ge=1)
    source_model_uri: str = Field(min_length=1)
    source_format: Literal["step", "stl", "glb"]
    operations: list[OptimizationInstruction] = Field(min_length=1)
    output_plan: SolidWorksOutputPlan

    @model_validator(mode="after")
    def validate_glb_source(self) -> "SolidWorksOptimizationContract":
        if self.source_format == "glb":
            raise ValueError(
                "GLB 源模型需先转换为 STL/STEP 再提交 SolidWorks；"
                "请在 OptimizationLoopService 中预处理"
            )
        return self


class SolidWorksExecutionResult(BaseModel):
    """SolidWorks 执行结果。"""
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "skipped", "invalid_geometry", "error"]
    step_path: str | None = None
    stl_path: str | None = None
    preview_paths: list[str] = Field(default_factory=list)
    review_report_path: str | None = None
    manifest_path: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class OptimizationIteration(BaseModel):
    """单次优化迭代的完整记录。"""
    model_config = ConfigDict(extra="forbid")

    iteration: int = Field(ge=1)
    feedback: OptimizationFeedback | None = None
    plan: OptimizationPlan | None = None
    solidworks_contract: SolidWorksOptimizationContract | None = None
    result: SolidWorksExecutionResult | None = None
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    status: Literal[
        "feedback_received",
        "planning",
        "planned",
        "executing",
        "completed",
        "failed",
    ] = "feedback_received"


# ── 请求 / 响应模型 ──

class SubmitOptimizationFeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    feedback_text: str = Field(min_length=1)
    target_component_id: str | None = None
    submitted_by: str = Field(min_length=1)


class AcceptOptimizationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    accepted: bool
    reviewed_by: str = Field(min_length=1)


class OptimizationLoopStatus(BaseModel):
    """优化闭环状态查询响应。"""
    model_config = ConfigDict(extra="forbid")
    pipeline_id: UUID
    state: str
    current_iteration: int
    total_iterations: int
    solidworks_available: bool
    iterations: list[OptimizationIteration] = Field(default_factory=list)
