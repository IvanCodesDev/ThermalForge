"""Typed contracts for the reproducible FOC arm thermal demo."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FocDemoThermal(BaseModel):
    state: str | None = None
    fidelity: str = "screening"
    backend: str = "lumped_estimator"
    not_cfd: bool = True
    metrics: dict[str, Any] = Field(default_factory=dict)
    recommended_parameters: dict[str, Any] = Field(default_factory=dict)
    geometry: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)


class FocDemoAsset(BaseModel):
    id: str
    provider: str
    kind: str
    filename: str
    url: str
    media_type: str
    size_bytes: int = Field(ge=0)


class FocDemoMeshStructure(BaseModel):
    file: str | None = None
    node_count: int = Field(default=0, ge=0)
    mesh_count: int = Field(default=0, ge=0)
    material_count: int = Field(default=0, ge=0)
    mesh_names: list[str] = Field(default_factory=list)
    interpretation: str = ""
    fidelity: str = "concept_mesh"
    manufacturable_cad: bool = False


class FocDemoStage(BaseModel):
    id: str
    label: str
    status: str
    detail: str = ""


class FocDemoHeatPath(BaseModel):
    name: str
    route: list[str] = Field(default_factory=list)
    why: str = ""
    evidence: list[str] = Field(default_factory=list)
    validation: str = ""


class FocDemoDecision(BaseModel):
    id: str
    title: str
    choice: str = ""
    why: str = ""
    tradeoff: str = ""
    evidence: list[str] = Field(default_factory=list)
    validation: str = ""
    confidence: str | float | None = None


class FocDemoDesign(BaseModel):
    source: str = "deterministic_fallback"
    architecture: str
    heat_paths: list[FocDemoHeatPath] = Field(default_factory=list)
    decisions: list[FocDemoDecision] = Field(default_factory=list)
    components: list[Any] = Field(default_factory=list)
    materials: list[Any] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    validation_tasks: list[str] = Field(default_factory=list)


class FocDemoSnapshot(BaseModel):
    run_id: str = "foc-arm-demo"
    generated_at: str | None = None
    scenario: str
    engineering_input: str = ""
    brief: dict[str, Any] = Field(default_factory=dict)
    configured_models: dict[str, Any] = Field(default_factory=dict)
    foc_simulation: dict[str, Any]
    thermal: FocDemoThermal
    assets: list[FocDemoAsset] = Field(default_factory=list)
    mesh_structure: FocDemoMeshStructure
    stages: list[FocDemoStage] = Field(default_factory=list)
    design: FocDemoDesign
    limitations: list[str] = Field(default_factory=list)
