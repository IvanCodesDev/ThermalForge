from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceRef(StrictModel):
    source_kind: Literal["document", "user_prompt", "clarification"]
    quote: str = Field(min_length=1, max_length=500)
    artifact_id: str | None = None
    chunk_id: str | None = None
    clarification_id: str | None = None
    page_number: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_reference(self) -> "EvidenceRef":
        if self.source_kind == "document" and (
            not self.artifact_id or not self.chunk_id
        ):
            raise ValueError("Document evidence requires artifact and chunk IDs.")
        if self.source_kind == "clarification" and not self.clarification_id:
            raise ValueError("Clarification evidence requires a clarification ID.")
        return self


class HeatSource(StrictModel):
    name: str = Field(min_length=1, max_length=160)
    power_w: float = Field(gt=0, le=100_000)
    maximum_temperature_c: float | None = Field(default=None, ge=-100, le=1_000)
    duty_cycle_percent: float | None = Field(default=None, gt=0, le=100)
    evidence: list[EvidenceRef] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class OperatingEnvironment(StrictModel):
    ambient_temp_c: float = Field(ge=-100, le=200)
    airflow_m_s: float | None = Field(default=None, ge=0, le=200)
    humidity_percent: float | None = Field(default=None, ge=0, le=100)
    evidence: list[EvidenceRef] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class Envelope(StrictModel):
    width_mm: float = Field(gt=0, le=100_000)
    height_mm: float = Field(gt=0, le=100_000)
    depth_mm: float = Field(gt=0, le=100_000)
    evidence: list[EvidenceRef] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class MassBudget(StrictModel):
    maximum_added_mass_g: float = Field(gt=0, le=1_000_000)
    maximum_added_mass_percent: float | None = Field(default=None, gt=0, le=100)
    evidence: list[EvidenceRef] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class Assumption(StrictModel):
    statement: str = Field(min_length=1, max_length=500)
    reason: str = Field(min_length=1, max_length=500)
    impact: Literal["low", "medium", "high"]
    requires_confirmation: bool = True


class EngineeringBrief(StrictModel):
    schema_version: str = "1.0"
    project_title: str = Field(min_length=1, max_length=200)
    heat_sources: list[HeatSource] = Field(default_factory=list)
    environment: OperatingEnvironment | None = None
    envelope: Envelope | None = None
    mass_budget: MassBudget | None = None
    mounting_constraints: list[str] = Field(default_factory=list)
    required_features: list[str] = Field(default_factory=list)
    prohibited_changes: list[str] = Field(default_factory=list)
    material_constraints: list[str] = Field(default_factory=list)
    manufacturing_constraints: list[str] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    missing_required_fields: list[str] = Field(default_factory=list)
    follow_up_question: str | None = None
    overall_confidence: float = Field(ge=0, le=1)


class ClarificationAnswer(StrictModel):
    answer: str = Field(min_length=1, max_length=4_000)


class ClarificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: str
    field_key: str
    question: str
    answer: str | None
    created_at: datetime
    answered_at: datetime | None
