from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from core.api.app import app
from core.workbench.contracts import EngineeringBrief, EvaluationResult, WorkbenchState
from core.workbench.extractor import extract_engineering_brief
from core.workbench.runtime import ConfirmationRequiredError, LocalWorkbenchRuntime
from core.workbench.state_machine import InvalidWorkbenchTransition, WorkbenchStateMachine


DATA = Path(__file__).resolve().parents[1] / "data"


def test_contracts_use_strict_pydantic_v2_validation():
    schema = EngineeringBrief.model_json_schema()
    assert schema["additionalProperties"] is False
    with pytest.raises(ValidationError):
        EngineeringBrief(source_text="需求", unknown_field=True)

    result = EvaluationResult(
        brief_id="7ff58f7e-36e2-4df8-9e0c-c3f4d59259c4",
        recommended_parameters={"structure_type": "flat"},
        svg="<svg></svg>",
        geometry={},
        metrics={},
        limitations=["screening only"],
    )
    assert result.fidelity == "screening"
    assert result.backend == "lumped_estimator"
    assert result.not_cfd is True


def test_state_machine_requires_confirmation_before_evaluating():
    awaiting = WorkbenchStateMachine(WorkbenchState.AWAITING_CONFIRMATION)
    assert awaiting.can_transition_to(WorkbenchState.CONFIRMED)
    assert not awaiting.can_transition_to(WorkbenchState.EVALUATING)
    with pytest.raises(InvalidWorkbenchTransition):
        awaiting.transition_to(WorkbenchState.EVALUATING)

    confirmed = awaiting.transition_to(WorkbenchState.CONFIRMED)
    assert confirmed.transition_to(WorkbenchState.EVALUATING).state == WorkbenchState.EVALUATING


def test_local_runtime_cannot_bypass_human_gate():
    runtime = LocalWorkbenchRuntime(DATA / "seed_library.json")
    brief = runtime.extract_brief("关节电机功耗 30W")

    with pytest.raises(ConfirmationRequiredError):
        runtime.evaluate_brief(brief.id)

    rejected = runtime.confirm_brief(brief.id, accepted=False, confirmed_by="user@example", expected_revision=1)
    assert rejected.state == WorkbenchState.REJECTED
    with pytest.raises(ConfirmationRequiredError):
        runtime.evaluate_brief(brief.id)


def test_deterministic_chinese_extraction():
    brief = extract_engineering_brief(
        "关节电机，尺寸 70x60x40 mm，功耗 35W，最高温 75℃，环境温度 30℃，"
        "重量上限 45g，铝6061，CNC，有风扇。"
    )

    assert brief.device_type == "关节电机"
    assert brief.dimensions == {"length_mm": 70.0, "width_mm": 60.0, "height_mm": 40.0}
    assert brief.power_w == 35.0
    assert brief.max_temp_c == 75.0
    assert brief.ambient_temp_c == 30.0
    assert brief.max_weight_g == 45.0
    assert brief.material == "铝6061"
    assert brief.manufacturing == "CNC"
    assert brief.has_fan is True
    assert brief.missing_fields == []


def test_foc_robot_joint_extraction_prefers_thermal_load_and_handles_negation():
    brief = extract_engineering_brief(
        "FOC机械臂关节，机械输出350W，持续热耗散按120W设计，160x140x110mm，"
        "环境温度35℃，MOSFET壳温目标低于85℃，质量不超过850g，铝6061，CNC，无独立风扇。"
    )
    assert brief.power_w == 120.0
    assert brief.max_temp_c == 85.0
    assert brief.max_weight_g == 850.0
    assert brief.has_fan is False


def test_deterministic_english_extraction_and_missing_defaults():
    brief = extract_engineering_brief(
        "Drone motor, 80 x 50 x 30 mm, power 120 W, maximum temperature 85 C, "
        "ambient 35 C, max weight 38 g, copper, 3D print, forced air."
    )

    assert brief.device_type == "无人机动力电机"
    assert brief.power_w == 120.0
    assert brief.max_temp_c == 85.0
    assert brief.ambient_temp_c == 35.0
    assert brief.max_weight_g == 38.0
    assert brief.material == "铜"
    assert brief.manufacturing == "3D打印"
    assert brief.has_fan is True
    assert brief.missing_fields == []

    defaulted = extract_engineering_brief("需要给一个设备散热")
    assert "power_w" in defaulted.missing_fields
    assert "dimensions" in defaulted.missing_fields
    assert defaulted.assumptions


def test_workbench_capabilities_and_confirmed_evaluation_api():
    client = TestClient(app)
    capabilities = client.get("/api/v1/workbench/capabilities")
    assert capabilities.status_code == 200
    assert capabilities.json() == {
        "runtime": "local",
        "adapter_boundary": "AgentWorkbenchAdapter",
        "external_agent_sdk_connected": False,
        "brief_extraction": "deterministic_keywords",
        "requires_human_confirmation": True,
        "evaluation_fidelity": "screening",
        "evaluation_backend": "lumped_estimator",
        "not_cfd": True,
        "supported_languages": ["zh-CN", "en"],
        "supported_structure_types": ["leaf_vein", "channel", "flat"],
    }

    extracted = client.post(
        "/api/v1/workbench/briefs/extract",
        json={"text": "关节电机 60x60x40 mm，功耗 28W，最高温 80℃，环境 25℃，重量上限 35g，铝6061，3D打印"},
    )
    assert extracted.status_code == 201
    brief = extracted.json()
    assert brief["state"] == "awaiting_confirmation"

    blocked = client.post("/api/v1/workbench/evaluations", json={"brief_id": brief["id"]})
    assert blocked.status_code == 409
    assert "必须先由用户明确确认" in blocked.json()["detail"]

    confirmed = client.post(
        f"/api/v1/workbench/briefs/{brief['id']}/confirm",
        json={"accepted": True, "confirmed_by": "api-test-user", "expected_revision": brief["revision"]},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["state"] == "confirmed"

    evaluated = client.post("/api/v1/workbench/evaluations", json={"brief_id": brief["id"]})
    assert evaluated.status_code == 200
    result = evaluated.json()
    assert result["fidelity"] == "screening"
    assert result["backend"] == "lumped_estimator"
    assert result["not_cfd"] is True
    assert result["state"] == "completed"
    assert result["recommended_parameters"]["structure_type"] in {"leaf_vein", "channel", "flat"}
    assert result["svg"].startswith("<svg")
    assert result["geometry"]["eff_area_mm2"] > 0
    assert result["metrics"]["t_hotspot_c"] > 0
    assert len(result["limitations"]) >= 3

    stored = client.get(f"/api/v1/workbench/briefs/{brief['id']}")
    assert stored.status_code == 200
    assert stored.json()["state"] == "completed"


def test_existing_api_remains_available():
    response = TestClient(app).post(
        "/generate",
        json={"params": {"structure_type": "flat", "length_scale": 60}},
    )
    assert response.status_code == 200
    assert response.json()["structure_type"] == "flat"
