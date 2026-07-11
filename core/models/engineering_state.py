"""版本化工程状态与产物登记契约。"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.models.agent_pipeline import EngineeringValue, EvidenceRef


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ValueStatus(StrEnum):
    EXTRACTED = "extracted"
    ASSUMED = "assumed"
    NEEDS_REVIEW = "needs_review"
    CONFIRMED = "confirmed"


T = TypeVar("T")


class TracedValue(StrictModel, Generic[T]):
    value: T
    status: ValueStatus
    evidence: list[EvidenceRef] = Field(min_length=1)


class Units(StrictModel):
    length: TracedValue[Literal["mm"]]
    angle: TracedValue[Literal["deg"]]
    temperature: TracedValue[Literal["C", "K"]]
    power: TracedValue[Literal["W"]]


class CoordinateSystem(StrictModel):
    handedness: TracedValue[Literal["right", "left"]]
    up_axis: TracedValue[Literal["x", "y", "z"]]
    origin_mm: TracedValue[tuple[float, float, float]]


class Joint(StrictModel):
    id: str = Field(min_length=1)
    axis: TracedValue[tuple[float, float, float]]
    rotation_range_deg: TracedValue[tuple[float, float]]
    outer_radius_mm: TracedValue[float]
    inner_radius_mm: TracedValue[float]
    axial_length_mm: TracedValue[float]
    shell_wall_thickness_mm: TracedValue[float]

    @model_validator(mode="after")
    def validate_geometry(self) -> "Joint":
        if self.inner_radius_mm.value >= self.outer_radius_mm.value:
            raise ValueError("inner_radius_mm 必须小于 outer_radius_mm")
        if self.shell_wall_thickness_mm.value <= 0:
            raise ValueError("shell_wall_thickness_mm 必须大于 0")
        if self.rotation_range_deg.value[0] > self.rotation_range_deg.value[1]:
            raise ValueError("rotation_range_deg 下限不得大于上限")
        if not any(self.axis.value):
            raise ValueError("axis 不能为零向量")
        return self


class Component(StrictModel):
    id: str = Field(min_length=1)
    name: TracedValue[str]
    category: TracedValue[str]
    dimensions: dict[str, EngineeringValue] = Field(default_factory=dict)
    material_id: TracedValue[str | None]


class Material(StrictModel):
    id: str = Field(min_length=1)
    name: TracedValue[str]
    properties: dict[str, EngineeringValue] = Field(default_factory=dict)


class Interface(StrictModel):
    id: str = Field(min_length=1)
    parent_component_id: TracedValue[str]
    child_component_id: TracedValue[str]
    mate_type: TracedValue[Literal["fixed", "concentric", "planar", "revolute"]]
    axis: TracedValue[tuple[float, float, float]]


class ThermalLoad(StrictModel):
    id: str = Field(min_length=1)
    component_id: TracedValue[str]
    heat_w: TracedValue[float]


class OperatingCase(StrictModel):
    id: str = Field(min_length=1)
    name: TracedValue[str]
    ambient_temperature_c: TracedValue[float]
    duty_cycle: TracedValue[float]
    thermal_load_ids: TracedValue[list[str]]


class Approval(StrictModel):
    id: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    decision: Literal["approved", "rejected"]
    reviewed_by: str = Field(min_length=1)
    revision: int = Field(ge=1)
    at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    evidence: list[EvidenceRef] = Field(min_length=1)


class UnresolvedItem(StrictModel):
    id: str = Field(min_length=1)
    description: TracedValue[str]


class EngineeringState(StrictModel):
    project_id: str = Field(min_length=1)
    revision: int = Field(default=1, ge=1)
    units: Units
    coordinate_system: CoordinateSystem
    joints: list[Joint] = Field(default_factory=list)
    components: list[Component] = Field(default_factory=list)
    materials: list[Material] = Field(default_factory=list)
    interfaces: list[Interface] = Field(default_factory=list)
    thermal_loads: list[ThermalLoad] = Field(default_factory=list)
    operating_cases: list[OperatingCase] = Field(default_factory=list)
    approvals: list[Approval] = Field(default_factory=list)
    unresolved: list[UnresolvedItem] = Field(default_factory=list)


class ArtifactFidelity(StrEnum):
    SOURCE = "source"
    ENGINEERING_PROXY = "engineering_proxy"
    CONCEPT_MESH = "concept_mesh"
    MANUFACTURING_CAD = "manufacturing_cad"
    METADATA = "metadata"


class Artifact(StrictModel):
    id: str = Field(min_length=1)
    role: str = Field(min_length=1)
    uri: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    fidelity: ArtifactFidelity
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    producer: str = Field(min_length=1)
    version: str = Field(min_length=1)
    input_revision: int = Field(ge=1)
    project_id: str | None = None
    parent_artifact_ids: tuple[str, ...] = ()
    execution_id: UUID | None = None
    handoff_id: str | None = None
    task_uuid: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    media_type: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def forbid_concept_mesh_as_manufacturing_cad(self) -> "Artifact":
        if self.role == "manufacturing_cad" and self.fidelity == ArtifactFidelity.CONCEPT_MESH:
            raise ValueError("concept_mesh 禁止登记为 manufacturing_cad")
        return self


class ArtifactLineage(StrictModel):
    project_id: str
    artifact: Artifact
    ancestors: list[Artifact] = Field(default_factory=list)


class ArtifactRegistry(StrictModel):
    project_id: str = Field(min_length=1)
    artifacts: list[Artifact] = Field(default_factory=list)


class PutEngineeringStateRequest(StrictModel):
    expected_revision: int = Field(ge=0)
    state: EngineeringState


class ConfirmEngineeringStateRequest(StrictModel):
    expected_revision: int = Field(ge=1)
    reviewed_by: str = Field(min_length=1)
    subject: str = "engineering_state"
    evidence: list[EvidenceRef] = Field(min_length=1)


class RegisterArtifactRequest(StrictModel):
    expected_revision: int = Field(ge=1)
    artifact: Artifact
