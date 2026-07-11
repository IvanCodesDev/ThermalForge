import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.engineering.schemas import (
    EngineeringBrief,
    Envelope,
    EvidenceRef,
    HeatSource,
    MassBudget,
    OperatingEnvironment,
)
from app.thermal.engine import calculate_thermal_analysis
from app.thermal.planning import build_analysis_plan, evaluate_candidates
from app.thermal.schemas import ThermalAnalysisRequest

FIXTURE_PATH = Path(__file__).parents[2] / "fixtures" / "thermal-analysis-v1.json"


@pytest.mark.parametrize(
    "case",
    json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["cases"],
    ids=lambda case: str(case["name"]),
)
def test_backend_engine_matches_typescript_golden_fixture(
    case: dict[str, Any],
) -> None:
    request = ThermalAnalysisRequest.model_validate(case["request"])

    result = calculate_thermal_analysis(
        request,
        generated_at=str(case["generatedAt"]),
    )

    assert result.model_dump(mode="json", by_alias=True) == case["expected"]


def test_rejects_invalid_or_unsorted_thermal_inputs() -> None:
    with pytest.raises(ValidationError):
        ThermalAnalysisRequest.model_validate(
            {
                "hardwareId": "robot-joint",
                "jointId": "knee",
                "heatSources": {"motor": 100},
                "constraints": [],
                "optimizationGoals": [],
                "inputs": {
                    "ambientTemperatureC": 80,
                    "initialTemperatureC": 25,
                    "thermalLimitC": 80,
                    "durationMinutes": 0.2,
                    "dutyCyclePercent": 101,
                    "airflowMps": -1,
                    "componentMassKg": 0,
                },
                "measurements": [
                    {"timeS": 10, "temperatureC": 30, "powerW": 10},
                    {"timeS": 5, "temperatureC": 31, "powerW": 10},
                    {"timeS": 20, "temperatureC": 32, "powerW": 10},
                ],
            }
        )


def test_builds_explicit_assumptions_and_filters_noncompliant_solutions() -> None:
    evidence = EvidenceRef(
        source_kind="user_prompt",
        quote="功率 120 W，环境 25°C，空间 180 × 90 × 70 mm，增重不超过 8%。",
    )
    brief = EngineeringBrief(
        project_title="机器人膝关节",
        heat_sources=[
            HeatSource(
                name="电机",
                power_w=120,
                maximum_temperature_c=85,
                evidence=[evidence],
                confidence=1,
            )
        ],
        environment=OperatingEnvironment(
            ambient_temp_c=25,
            evidence=[evidence],
            confidence=1,
        ),
        envelope=Envelope(
            width_mm=180,
            height_mm=90,
            depth_mm=70,
            evidence=[evidence],
            confidence=1,
        ),
        mass_budget=MassBudget(
            maximum_added_mass_g=150,
            maximum_added_mass_percent=8,
            evidence=[evidence],
            confidence=1,
        ),
        mounting_constraints=["不得超出运动包络"],
        required_features=["外壳可拆卸"],
        overall_confidence=0.95,
    )

    plan = build_analysis_plan(brief)
    analysis = calculate_thermal_analysis(
        plan.request,
        generated_at="2026-07-11T00:00:00.000Z",
    )
    evaluations = evaluate_candidates(
        brief=brief,
        request=plan.request,
        analysis=analysis,
    )
    evaluations_by_id = {
        evaluation.solution_id: evaluation for evaluation in evaluations
    }

    assert plan.request.inputs.thermal_limit_c == 85
    assert plan.request.inputs.airflow_mps == 0.1
    assert plan.request.inputs.component_mass_kg == 1.8
    assert {assumption.key for assumption in plan.assumptions} >= {
        "initial_temperature_c",
        "duration_minutes",
        "airflow_mps",
        "component_mass_kg",
    }
    assert evaluations_by_id["vein-bridge"].eligible is True
    assert evaluations_by_id["pin-fin"].eligible is False
    assert "motion_envelope_risk" in evaluations_by_id["pin-fin"].rejection_codes
    assert evaluations_by_id["gyroid"].eligible is False
    assert "mass_budget_exceeded" in evaluations_by_id["gyroid"].rejection_codes
    assert all(0 <= evaluation.cost_score <= 100 for evaluation in evaluations)
    assert all(0 <= evaluation.risk_score <= 100 for evaluation in evaluations)
