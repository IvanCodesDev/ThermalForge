from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _to_camel(value: str) -> str:
    first, *remaining = value.split("_")
    return first + "".join(part.capitalize() for part in remaining)


class CamelStrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        alias_generator=_to_camel,
        allow_inf_nan=False,
    )


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class AnalysisInputs(CamelStrictModel):
    ambient_temperature_c: float = Field(ge=-40, le=100)
    initial_temperature_c: float = Field(ge=-40, le=200)
    thermal_limit_c: float = Field(le=250)
    duration_minutes: float = Field(ge=0.5, le=120)
    duty_cycle_percent: float = Field(ge=1, le=100)
    airflow_mps: float = Field(ge=0, le=20)
    component_mass_kg: float = Field(gt=0, le=100)

    @model_validator(mode="after")
    def validate_temperature_limit(self) -> "AnalysisInputs":
        if self.thermal_limit_c <= self.ambient_temperature_c:
            raise ValueError("Thermal limit must be higher than ambient temperature.")
        return self


class MeasurementPoint(CamelStrictModel):
    time_s: float = Field(ge=0)
    temperature_c: float = Field(ge=-100, le=1_000)
    power_w: float = Field(ge=0, le=100_000)


class ThermalCurvePoint(CamelStrictModel):
    time_s: float = Field(ge=0)
    temperature_c: float = Field(ge=-100, le=10_000)
    power_w: float | None = Field(
        default=None,
        ge=0,
        le=100_000,
        exclude_if=lambda value: value is None,
    )


class ThermalCaseResult(CamelStrictModel):
    curve: list[ThermalCurvePoint] = Field(min_length=1, max_length=5_001)
    max_temperature_c: float
    time_to_limit_minutes: float | None
    thermal_resistance_k_per_w: float = Field(gt=0)
    effective_capacity_j_per_k: float = Field(gt=0)


InterferenceRisk = Literal["低", "中", "高"]
RecommendationGrade = Literal["A", "B", "C", "D"]
RiskLevel = Literal["Low", "Medium", "High"]


class CandidateResult(ThermalCaseResult):
    solution_id: str = Field(min_length=1, max_length=80)
    score: float = Field(ge=0, le=100)
    grade: RecommendationGrade
    added_mass_percent: float = Field(ge=0, le=100)
    interference_risk: InterferenceRisk
    hotspot_reduction_c: float
    time_to_limit_improvement_percent: float | None


class ThermalAnalysisRequest(CamelStrictModel):
    hardware_id: str = Field(min_length=1, max_length=80)
    joint_id: str = Field(min_length=1, max_length=80)
    heat_sources: dict[str, float] = Field(max_length=100)
    constraints: list[str] = Field(default_factory=list, max_length=100)
    optimization_goals: list[str] = Field(default_factory=list, max_length=50)
    inputs: AnalysisInputs
    measurements: list[MeasurementPoint] = Field(default_factory=list, max_length=5_000)

    @model_validator(mode="after")
    def validate_sources_and_measurements(self) -> "ThermalAnalysisRequest":
        if any(power < 0 or power > 100_000 for power in self.heat_sources.values()):
            raise ValueError("Heat-source power must be between 0 and 100000 W.")
        if sum(self.heat_sources.values()) <= 0 and not self.measurements:
            raise ValueError("At least one positive heat source is required.")
        if self.measurements and len(self.measurements) < 3:
            raise ValueError("Measured calibration requires at least three points.")
        if self.measurements:
            average_power = sum(point.power_w for point in self.measurements) / len(
                self.measurements
            )
            if average_power <= 0:
                raise ValueError("Measured average power must be positive.")
        if any(
            current.time_s <= previous.time_s
            for previous, current in zip(
                self.measurements,
                self.measurements[1:],
                strict=False,
            )
        ):
            raise ValueError("Measurement time must increase strictly.")
        return self


class ThermalAnalysisResult(CamelStrictModel):
    id: str = Field(min_length=1, max_length=200)
    generated_at: str = Field(min_length=1, max_length=80)
    source: Literal["engineering-estimate", "measured-calibrated"]
    method_label: str = Field(min_length=1, max_length=200)
    total_power_w: float = Field(gt=0)
    baseline: ThermalCaseResult
    candidates: list[CandidateResult] = Field(min_length=1)
    recommended_solution_id: str = Field(min_length=1, max_length=80)
    risk_level: RiskLevel
    warnings: list[str]


class AnalysisAssumption(StrictModel):
    key: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=500)
    reason: str = Field(min_length=1, max_length=500)
    impact: Literal["low", "medium", "high"]
    requires_confirmation: bool = True


class AnalysisPlan(StrictModel):
    request: ThermalAnalysisRequest
    assumptions: list[AnalysisAssumption]


class CandidateEvaluation(StrictModel):
    solution_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=200)
    eligible: bool
    rejection_codes: list[str]
    thermal_score: float = Field(ge=0, le=100)
    cost_score: float = Field(ge=0, le=100)
    risk_score: float = Field(ge=0, le=100)
    added_mass_g: float = Field(ge=0)
    added_mass_percent: float = Field(ge=0, le=100)
    max_temperature_c: float
    hotspot_reduction_c: float
    interference_risk: InterferenceRisk


class ComponentExplanation(StrictModel):
    component_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,79}$")
    name: str = Field(min_length=1, max_length=120)
    explanation: str = Field(min_length=1, max_length=1_000)


class DesignRisk(StrictModel):
    source: Literal[
        "engineering_brief",
        "thermal_analysis",
        "solution_catalog",
        "llm_assessment",
    ]
    description: str = Field(min_length=1, max_length=1_000)
    impact: Literal["low", "medium", "high"]
    recommended_action: str = Field(min_length=1, max_length=1_000)


class ThermalOptimizationDecision(StrictModel):
    selected_solution_id: str = Field(min_length=1, max_length=80)
    rationale: str = Field(min_length=1, max_length=2_000)
    heat_transfer_path: list[str] = Field(min_length=2, max_length=20)
    material_recommendations: list[str] = Field(min_length=1, max_length=20)
    geometry_anchors: list[str] = Field(min_length=1, max_length=30)
    manufacturing_recommendations: list[str] = Field(min_length=1, max_length=20)
    component_explanations: list[ComponentExplanation] = Field(
        min_length=1,
        max_length=30,
    )
    risks: list[DesignRisk] = Field(default_factory=list, max_length=30)
    unverified_items: list[str] = Field(default_factory=list, max_length=50)
    requires_human_confirmation: bool = False


class SelectedThermalSolution(StrictModel):
    solution_id: str
    title: str
    tag: str
    features: list[str]
    score: float = Field(ge=0, le=100)
    grade: RecommendationGrade
    max_temperature_c: float
    time_to_limit_minutes: float | None
    thermal_resistance_k_per_w: float = Field(gt=0)
    effective_capacity_j_per_k: float = Field(gt=0)
    added_mass_g: float = Field(ge=0)
    added_mass_percent: float = Field(ge=0, le=100)
    interference_risk: InterferenceRisk
    hotspot_reduction_c: float
    time_to_limit_improvement_percent: float | None
    cost_score: float = Field(ge=0, le=100)
    risk_score: float = Field(ge=0, le=100)


class GenerationBrief(StrictModel):
    design_intent: str = Field(min_length=1, max_length=2_000)
    positive_constraints: list[str] = Field(min_length=1, max_length=100)
    negative_constraints: list[str] = Field(default_factory=list, max_length=100)


class ThermalDesignSpec(StrictModel):
    schema_version: str = "1.0"
    task_id: str
    engineering_brief_artifact_id: str
    thermal_analysis_artifact_id: str
    analysis_id: str
    baseline_max_temperature_c: float
    baseline_time_to_limit_minutes: float | None
    selected_solution: SelectedThermalSolution
    candidate_evaluations: list[CandidateEvaluation]
    rationale: str
    heat_transfer_path: list[str]
    material_recommendations: list[str]
    geometry_anchors: list[str]
    manufacturing_recommendations: list[str]
    component_explanations: list[ComponentExplanation]
    generation_brief: GenerationBrief
    assumptions: list[AnalysisAssumption]
    risks: list[DesignRisk]
    unverified_items: list[str]
    requires_human_confirmation: bool
