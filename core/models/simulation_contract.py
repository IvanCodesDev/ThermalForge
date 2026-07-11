"""严格的仿真交接与结果契约。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class UnitSystem(StrictModel):
    length: Literal["mm"]
    angle: Literal["deg"]
    temperature: Literal["C", "K"]
    power: Literal["W"]
    pressure: Literal["Pa"]
    stress: Literal["Pa", "MPa"]


class CoordinateSystem(StrictModel):
    handedness: Literal["right", "left"]
    up_axis: Literal["x", "y", "z"]
    origin_mm: tuple[float, float, float]


class GeometryGenerator(StrictModel):
    provider: Literal["spaceclaim"]
    api_version: Literal["V251"]
    script_uri: str = Field(min_length=1)
    output_geometry_uri: str = Field(min_length=1)
    artifact_id: str = Field(min_length=1)
    fidelity: Literal["engineering_proxy", "manufacturing_cad"]


class FinParameters(StrictModel):
    count: int = Field(ge=0)
    height_mm: float = Field(ge=0)
    thickness_mm: float = Field(ge=0)
    pitch_deg: float = Field(gt=0, le=360)


class JointParameters(StrictModel):
    id: str = Field(min_length=1)
    outer_radius_mm: float = Field(gt=0)
    inner_radius_mm: float = Field(ge=0)
    axial_length_mm: float = Field(gt=0)
    segment_angle_deg: float = Field(gt=0, le=360)
    shell_wall_thickness_mm: float = Field(gt=0)
    axis: tuple[float, float, float]
    fins: FinParameters

    @model_validator(mode="after")
    def validate_geometry(self) -> "JointParameters":
        if self.inner_radius_mm >= self.outer_radius_mm:
            raise ValueError("inner_radius_mm 必须小于 outer_radius_mm")
        if not any(self.axis):
            raise ValueError("axis 不能为零向量")
        return self


class MaterialProperties(StrictModel):
    material_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    density_kg_m3: float = Field(gt=0)
    thermal_conductivity_w_mk: float = Field(gt=0)
    specific_heat_j_kgk: float = Field(gt=0)
    coefficient_thermal_expansion_1_k: float = Field(ge=0)
    youngs_modulus_pa: float = Field(gt=0)
    poissons_ratio: float = Field(gt=-1, lt=0.5)
    yield_strength_pa: float = Field(gt=0)
    ultimate_tensile_strength_pa: float = Field(gt=0)


class ThermalLoad(StrictModel):
    id: str = Field(min_length=1)
    named_selection: str = Field(min_length=1)
    load_type: Literal["heat_power", "heat_flux", "temperature", "convection"]
    magnitude: float
    unit: Literal["W", "W/m2", "C", "K", "W/m2K"]


class Contact(StrictModel):
    id: str = Field(min_length=1)
    source_named_selection: str = Field(min_length=1)
    target_named_selection: str = Field(min_length=1)
    contact_type: Literal["bonded", "frictional", "frictionless", "thermal"]
    thermal_conductance_w_m2k: float | None = Field(default=None, gt=0)
    friction_coefficient: float | None = Field(default=None, ge=0)


class OperatingCase(StrictModel):
    id: str = Field(min_length=1)
    ambient_temperature_c: float
    thermal_load_ids: list[str] = Field(min_length=1)
    inlet_mass_flow_kg_s: float | None = Field(default=None, gt=0)
    inlet_pressure_pa: float | None = Field(default=None, gt=0)
    rotational_speed_rpm: float | None = Field(default=None, ge=0)


class NamedSelection(StrictModel):
    name: str = Field(min_length=1)
    purpose: Literal["load", "contact", "inlet", "outlet", "support", "result", "fluid", "solid"]
    entity_type: Literal["body", "face", "edge", "vertex"]


class MeshPlan(StrictModel):
    physics: Literal["lumped", "thermal", "CFD", "FEA", "coupled_CFD_FEA"]
    element_order: Literal["none", "linear", "quadratic"]
    global_size_mm: float | None = Field(default=None, gt=0)
    boundary_layers: int = Field(default=0, ge=0)
    convergence_study_required: bool


class SolverPlan(StrictModel):
    solver: str = Field(min_length=1)
    analysis_type: Literal["lumped", "steady_thermal", "transient_thermal", "CFD", "static_structural", "coupled_CFD_FEA"]
    max_iterations: int = Field(gt=0)
    residual_target: float = Field(gt=0)


class AcceptanceCriteria(StrictModel):
    max_temperature_c: float
    max_pressure_drop_pa: float | None = Field(default=None, gt=0)
    min_safety_factor: float | None = Field(default=None, gt=0)
    require_converged: bool = True


class SimulationHandoffContract(StrictModel):
    schema: Literal["thermalforge.simulation_handoff"]
    version: Literal["1.0.0"]
    project_id: str = Field(min_length=1)
    engineering_revision: int = Field(ge=1)
    created_by: str = Field(min_length=1)
    model: Literal["lumped", "CFD", "FEA", "coupled_CFD_FEA"]
    approval_status: Literal["approved"]
    units: UnitSystem
    coordinate_system: CoordinateSystem
    geometry_generator: GeometryGenerator
    joints: list[JointParameters] = Field(min_length=1)
    materials: list[MaterialProperties] = Field(min_length=1)
    thermal_loads: list[ThermalLoad] = Field(min_length=1)
    contacts: list[Contact]
    operating_cases: list[OperatingCase] = Field(min_length=1)
    named_selections: list[NamedSelection] = Field(min_length=1)
    mesh_plan: MeshPlan
    solver_plan: SolverPlan
    acceptance: AcceptanceCriteria


class AcceptanceViolation(StrictModel):
    code: str
    case_id: str | None = None
    message: str


class ResultAcceptance(StrictModel):
    status: Literal["passed", "review_required"]
    violations: list[AcceptanceViolation] = Field(default_factory=list)
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ResultArtifact(StrictModel):
    role: Literal["report", "field_data", "mesh", "log", "image"]
    uri: str = Field(min_length=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class CaseResult(StrictModel):
    case_id: str = Field(min_length=1)
    converged: bool
    max_temperature_c: float
    pressure_drop_pa: float | None = Field(default=None, ge=0)
    max_von_mises_stress_pa: float | None = Field(default=None, ge=0)
    min_safety_factor: float | None = Field(default=None, gt=0)


class CompileSimulationHandoffRequest(StrictModel):
    engineering_revision: int = Field(ge=1)
    geometry_artifact_id: str = Field(min_length=1)
    created_by: str = Field(min_length=1)
    model: Literal["lumped", "CFD", "FEA", "coupled_CFD_FEA"]
    joint_extensions: dict[str, dict[str, Any]]
    named_selections: list[dict[str, Any]]
    contacts: list[dict[str, Any]] = Field(default_factory=list)
    mesh_plan: dict[str, Any]
    solver_plan: dict[str, Any]
    acceptance: dict[str, Any]


class RegisterSpaceClaimArtifactsRequest(StrictModel):
    artifacts: list[dict[str, Any]] = Field(min_length=1)


class SimulationResultContract(StrictModel):
    schema: Literal["thermalforge.simulation_result"]
    version: Literal["1.0.0"]
    project_id: str = Field(min_length=1)
    engineering_revision: int = Field(ge=1)
    handoff_id: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    model: Literal["lumped", "CFD", "FEA", "coupled_CFD_FEA"]
    solver: str = Field(min_length=1)
    cases: list[CaseResult] = Field(min_length=1)
    artifacts: list[ResultArtifact]
    warnings: list[str]

    @field_validator("created_at", mode="before")
    @classmethod
    def parse_json_timestamp(cls, value: Any) -> Any:
        """Allow the ISO-8601 representation used by real JSON transports."""
        if isinstance(value, str):
            normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                raise ValueError("created_at must include a timezone")
            return parsed
        return value

    @model_validator(mode="after")
    def validate_model_results(self) -> "SimulationResultContract":
        for case in self.cases:
            if self.model == "lumped" and (case.pressure_drop_pa is not None or case.max_von_mises_stress_pa is not None):
                raise ValueError("lumped 结果不得声明 CFD/FEA 场结果")
            if self.model in {"CFD", "coupled_CFD_FEA"} and case.pressure_drop_pa is None:
                raise ValueError("CFD 结果必须包含 pressure_drop_pa")
            if self.model in {"FEA", "coupled_CFD_FEA"} and (
                case.max_von_mises_stress_pa is None or case.min_safety_factor is None
            ):
                raise ValueError("FEA 结果必须包含应力和安全系数")
        return self
