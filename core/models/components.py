"""概念 3D 分件后的组件、装配与工程分析契约。"""
from __future__ import annotations

from enum import Enum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ReviewStatus(str, Enum):
    PROPOSED = "proposed"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class GeometrySummary(BaseModel):
    vertex_count: int | None = Field(default=None, ge=0)
    triangle_count: int | None = Field(default=None, ge=0)
    connected_components: int | None = Field(default=None, ge=1)
    bbox_mm: tuple[float, float, float] | None = None
    volume_mm3: float | None = Field(default=None, ge=0)
    surface_area_mm2: float | None = Field(default=None, ge=0)
    centroid_mm: tuple[float, float, float] | None = None


class MaterialCandidate(BaseModel):
    name: str
    confidence: float = Field(ge=0, le=1)
    visual_evidence: list[str] = Field(default_factory=list)
    engineering_basis: list[str] = Field(default_factory=list)
    thermal_conductivity_w_mk: float | None = Field(default=None, gt=0)
    density_kg_m3: float | None = Field(default=None, gt=0)


class ComponentAsset(BaseModel):
    url: str
    filename: str
    format: str
    preview_urls: list[str] = Field(default_factory=list)


class ComponentRecord(BaseModel):
    component_id: UUID = Field(default_factory=uuid4)
    source_part_index: int = Field(ge=0)
    asset: ComponentAsset
    display_name: str
    semantic_type: str
    alternative_types: list[str] = Field(default_factory=list)
    geometry: GeometrySummary = Field(default_factory=GeometrySummary)
    material_candidates: list[MaterialCandidate] = Field(default_factory=list)
    recommended_material: str | None = None
    thermal_role: str
    structural_role: str
    manufacturing_processes: list[str] = Field(default_factory=list)
    design_rationale: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    validation_tasks: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    review_status: ReviewStatus = ReviewStatus.NEEDS_REVIEW
    requires_material_confirmation: Literal[True] = True


class AssemblyRelation(BaseModel):
    source_component_id: UUID
    target_component_id: UUID
    relation: Literal["contains", "supports", "contacts", "fastens", "seals", "routes_flow_to", "unknown"]
    confidence: float = Field(ge=0, le=1)
    evidence: list[str] = Field(default_factory=list)


class ComponentManifest(BaseModel):
    model_id: UUID = Field(default_factory=uuid4)
    decomposition_task_uuid: str
    decomposition_provider: Literal["hyper3d_bang"] = "hyper3d_bang"
    source_model_url: str | None = None
    strength: int = Field(ge=2, le=12)
    components: list[ComponentRecord]
    relations: list[AssemblyRelation] = Field(default_factory=list)
    review_status: ReviewStatus = ReviewStatus.NEEDS_REVIEW
    fidelity: Literal["concept_mesh"] = "concept_mesh"
    material_disclaimer: str = "材料为 AI 候选，不代表已从概念网格证明真实工程材料。"
    engineering_disclaimer: str = "组件作用与制造评价需结合工程文档、确定性 CAD 和仿真结果复核。"
