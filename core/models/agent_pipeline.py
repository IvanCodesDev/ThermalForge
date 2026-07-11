"""数据手册到 Hyper3D 展示资产的 Agent 编排契约。"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PipelineState(StrEnum):
    INGESTED = "ingested"
    SPEC_REVIEW = "spec_review"
    SPEC_CONFIRMED = "spec_confirmed"
    GEOMETRY_READY = "geometry_ready"
    HYPER3D_READY = "hyper3d_ready"
    HYPER3D_SUBMITTED = "hyper3d_submitted"
    HYPER3D_DONE = "hyper3d_done"
    # ── SolidWorks 优化反馈闭环 ──
    OPTIMIZATION_REVIEW = "optimization_review"
    OPTIMIZATION_PLANNED = "optimization_planned"
    SOLIDWORKS_SUBMITTED = "solidworks_submitted"
    SOLIDWORKS_DONE = "solidworks_done"
    # ── 终态 ──
    VALIDATION_REVIEW = "validation_review"
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"


class SourceKind(StrEnum):
    DATASHEET = "datasheet"
    STEP = "step"
    IMAGE = "image"
    TEXT = "text"
    MODEL = "model"


class EvidenceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str
    locator: str
    excerpt: str | None = None


class EngineeringValue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: float | str | list[float] | None = None
    unit: str | None = None
    confidence: float = Field(default=0.0, ge=0, le=1)
    status: Literal["extracted", "assumed", "needs_review", "confirmed"] = "needs_review"
    evidence: list[EvidenceRef] = Field(default_factory=list)


class SourceAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    kind: SourceKind
    uri: str
    filename: str
    media_type: str | None = None


class AssemblyInterface(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    parent_component_id: str
    child_component_id: str
    mate_type: Literal["fixed", "concentric", "planar", "revolute"]
    axis: tuple[float, float, float] = (0.0, 0.0, 1.0)
    offset_mm: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation_deg: tuple[float, float, float] = (0.0, 0.0, 0.0)
    clearance_mm: float = Field(default=0.5, ge=0)
    confidence: float = Field(default=0.0, ge=0, le=1)
    evidence: list[EvidenceRef] = Field(default_factory=list)


class ComponentSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    category: Literal["shell", "motor", "reducer", "electronics", "structure", "fastener", "other"]
    dimensions: dict[str, EngineeringValue] = Field(default_factory=dict)
    material: EngineeringValue = Field(default_factory=EngineeringValue)
    heat_loss_w: EngineeringValue = Field(default_factory=EngineeringValue)
    source_asset_ids: list[str] = Field(default_factory=list)


class EngineeringSpecification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(default=1, ge=1)
    product_name: str
    overall_bbox_mm: tuple[float, float, float] | None = None
    components: list[ComponentSpec] = Field(default_factory=list)
    interfaces: list[AssemblyInterface] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)


class ComponentSemanticCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    component_id: str
    semantic_type: str
    confidence: float = Field(ge=0, le=1)
    rationale: str


class Hyper3DGenerationContract(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Literal["hyper3d"] = "hyper3d"
    endpoint: Literal["rodin"] = "rodin"
    tier: Literal["Gen-2"] = "Gen-2"
    prompt: str
    image_asset_ids: list[str] = Field(default_factory=list, max_length=5)
    bbox_condition: tuple[float, float, float] | None = None
    geometry_file_format: Literal["glb", "usdz", "fbx", "obj", "stl"] = "glb"
    material: Literal["PBR", "Shaded", "All", "None"] = "PBR"
    mesh_mode: Literal["Quad", "Raw"] = "Quad"
    quality: Literal["high", "medium", "low", "extra-low"] = "high"
    preview_render: bool = True


class ValidationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    overall_bbox_error_pct: float | None = None
    joint_axis_error_mm: float | None = None
    keep_out_collision_count: int = Field(default=0, ge=0)
    passed: bool = False
    findings: list[str] = Field(default_factory=list)


class PipelineArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    role: Literal["engineering_step", "engineering_glb", "reference_render", "hyper3d_glb", "hyper3d_preview", "bang_glb", "manifest", "solidworks_step", "solidworks_stl", "solidworks_preview", "optimization_manifest"]
    uri: str
    provider: str
    fidelity: Literal["source", "engineering_proxy", "concept_mesh", "metadata", "optimized_cad", "optimized_mesh"]
    task_uuid: str | None = None


class AgentEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent: str
    agent_version: str | None = None
    prompt_id: str | None = None
    prompt_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    model: str | None = None
    skills: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    action: str
    state: PipelineState
    at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    detail: dict[str, Any] = Field(default_factory=dict)


class AgentPipeline(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID = Field(default_factory=uuid4)
    state: PipelineState = PipelineState.INGESTED
    revision: int = Field(default=1, ge=1)
    sources: list[SourceAsset]
    specification: EngineeringSpecification | None = None
    component_semantic_candidates: list[ComponentSemanticCandidate] = Field(default_factory=list)
    hyper3d_contract: Hyper3DGenerationContract | None = None
    hyper3d_task_uuid: str | None = None
    validation: ValidationReport | None = None
    artifacts: list[PipelineArtifact] = Field(default_factory=list)
    events: list[AgentEvent] = Field(default_factory=list)
    requires_human_confirmation: Literal[True] = True
    # ── SolidWorks 优化闭环 ──
    optimization_iterations: list[Any] = Field(default_factory=list)
    current_optimization_iteration: int = Field(default=0, ge=0)
    solidworks_contract: Any | None = None


class CreatePipelineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_name: str = Field(min_length=1)
    sources: list[SourceAsset] = Field(min_length=1)
    initial_requirements: str = ""


class ProposeSpecificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    specification: EngineeringSpecification


class ExtractSpecificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_contents: dict[str, str] = Field(default_factory=dict)


class SpecificationExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    specification: EngineeringSpecification
    component_semantic_candidates: list[ComponentSemanticCandidate] = Field(default_factory=list)


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    accepted: bool
    reviewed_by: str = Field(min_length=1)
    expected_revision: int = Field(ge=1)


class RegisterGeometryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    artifacts: list[PipelineArtifact] = Field(min_length=1)

    @model_validator(mode="after")
    def require_engineering_geometry(self) -> "RegisterGeometryRequest":
        if not any(item.fidelity == "engineering_proxy" for item in self.artifacts):
            raise ValueError("必须至少提供一个 engineering_proxy 产物")
        return self


class RegisterHyper3DResultRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_uuid: str = Field(min_length=1)
    artifacts: list[PipelineArtifact] = Field(min_length=1)

    @model_validator(mode="after")
    def require_hyper3d_asset(self) -> "RegisterHyper3DResultRequest":
        concept_meshes = [
            item for item in self.artifacts
            if item.provider == "hyper3d" and item.fidelity == "concept_mesh"
        ]
        if not concept_meshes:
            raise ValueError("必须提供来源为 hyper3d 的 concept_mesh 产物")
        if any(item.task_uuid != self.task_uuid for item in concept_meshes):
            raise ValueError("concept_mesh 必须记录与结果一致的 Hyper3D task UUID")
        return self


class SubmitHyper3DRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_uuid: str = Field(min_length=1)


class PipelineStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    state: PipelineState
    revision: int
    requires_human_confirmation: Literal[True] = True
    ready_for_hyper3d: bool
    hyper3d_task_uuid: str | None = None
    validation_passed: bool | None = None


class FrontendPipelineManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pipeline_id: UUID
    revision: int
    state: PipelineState
    product_name: str
    engineering_proxy: list[PipelineArtifact]
    reference_renders: list[PipelineArtifact]
    concept_meshes: list[PipelineArtifact]
    validation: ValidationReport | None = None
    disclaimer: str = "concept_mesh 仅用于概念展示，不是可制造 CAD；工程尺寸以 engineering_proxy 为准。"
