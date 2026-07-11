from __future__ import annotations

import json
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from core.api.app import app
from core.api.routes.foc_demo import get_foc_demo_repository
from core.api.routes.models import get_openai_client
from core.config import Settings
from core.providers.openai_models import OpenAIModelsClient
from core.services.foc_demo import FocDemoRepository


def _repository(tmp_path: Path) -> FocDemoRepository:
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "rodin.glb").write_bytes(b"glTF-demo")
    (assets / "bang.glb").write_bytes(b"glTF-parts")
    output = tmp_path / "backend.json"
    output.write_text(
        json.dumps(
            {
                "generated_at": "2026-07-10T17:31:10+00:00",
                "scenario": "FOC 六轴协作机械臂肘关节热设计",
                "configured_models": {"text_model": "gpt-5.6-sol"},
                "engineering_input": "48V PMSM，持续 120W，峰值 220W。",
                "confirmed_brief": {"state": "confirmed", "power_w": 120, "max_temp_c": 85},
                "screening_evaluation": {
                    "fidelity": "screening",
                    "backend": "lumped_estimator",
                    "not_cfd": True,
                    "metrics": {"t_hotspot_c": 159.56},
                    "limitations": ["不是 CFD"],
                },
                "external_calls": {
                    "gpt_5_6_sol": {"status": "success", "api_key": "must-not-leak"},
                    "hyper3d_rodin": {
                        "status": "done",
                        "response": {"jobs": {"subscription_key": "must-not-leak"}},
                        "local_assets": [
                            {"name": "rodin.glb", "local_path": "outputs/foc_robot_arm_assets/rodin.glb"}
                        ],
                    },
                    "hyper3d_bang": {
                        "status": "done",
                        "local_assets": [
                            {"name": "bang.glb", "local_path": "outputs/foc_robot_arm_assets/bang.glb"}
                        ],
                    },
                },
                "bang_glb_structure": {"node_count": 4, "mesh_count": 3, "mesh_names": ["root.0", "root.1", "root.2"]},
                "disclaimers": ["概念网格不是可制造 CAD"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return FocDemoRepository(
        output_path=output,
        asset_dir=assets,
        reasoning_path=tmp_path / "reasoning.json",
    )


def test_foc_demo_snapshot_and_raw_routes_include_simulation_without_secrets(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    app.dependency_overrides[get_foc_demo_repository] = lambda: repository
    client = TestClient(app)
    try:
        snapshot = client.get("/api/v1/foc-demo")
        raw = client.get("/api/v1/foc-demo/raw")
    finally:
        app.dependency_overrides.clear()

    assert snapshot.status_code == 200
    payload = snapshot.json()
    assert payload["run_id"] == "foc-arm-demo"
    assert payload["foc_simulation"]["total_continuous_loss_w"] == 120
    assert payload["foc_simulation"]["total_peak_loss_w"] == 220
    assert payload["thermal"]["not_cfd"] is True
    assert raw.status_code == 200
    assert "must-not-leak" not in raw.text
    assert "subscription_key" not in raw.text


def test_foc_demo_asset_route_serves_only_discovered_local_assets(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    app.dependency_overrides[get_foc_demo_repository] = lambda: repository
    client = TestClient(app)
    try:
        model = client.get("/api/v1/foc-demo/assets/rodin.glb")
        unknown = client.get("/api/v1/foc-demo/assets/not-listed.glb")
        traversal = client.get("/api/v1/foc-demo/assets/..%2Fbackend.json")
    finally:
        app.dependency_overrides.clear()

    assert model.status_code == 200
    assert model.content == b"glTF-demo"
    assert model.headers["content-type"].startswith("model/gltf-binary")
    assert unknown.status_code == 404
    assert traversal.status_code == 404


def test_reasoning_route_persists_auditable_decision_ledger(tmp_path: Path) -> None:
    repository = _repository(tmp_path)

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert request.url.path == "/v1/responses"
        assert body["model"] == "gpt-5.6-sol"
        assert "foc_simulation" in body["input"]
        return httpx.Response(
            200,
            json={
                "id": "resp_reasoning",
                "status": "completed",
                "output_text": json.dumps(
                    {
                        "architecture": "双热源双路径，预留液冷升级",
                        "heat_paths": [
                            {
                                "name": "逆变器",
                                "route": ["MOSFET", "TIM", "冷板", "壳体"],
                                "why": "缩短界面热路径",
                                "evidence": ["36W 逆变器预算"],
                                "validation": "热电偶与 CFD",
                            }
                        ],
                        "decisions": [
                            {
                                "id": "cold-plate",
                                "title": "独立驱动器冷板",
                                "choice": "可拆卸 6061 冷板",
                                "why": "便于控制 TIM 压紧与返修",
                                "tradeoff": "增加紧固件和界面热阻",
                                "evidence": ["MOSFET 壳温上限 85°C"],
                                "validation": "接触热阻测试",
                                "confidence": "high",
                            }
                        ],
                        "risks": ["自然对流余量不足"],
                        "validation_tasks": ["建立双热源共轭传热 CFD"],
                    },
                    ensure_ascii=False,
                ),
            },
        )

    settings = Settings(
        OPENAI_API_KEY="test-key",
        OPENAI_BASE_URL="https://provider.test/v1",
        OPENAI_TEXT_MODEL="gpt-5.6-sol",
    )
    app.dependency_overrides[get_foc_demo_repository] = lambda: repository
    app.dependency_overrides[get_openai_client] = lambda: OpenAIModelsClient(
        settings,
        httpx.MockTransport(handler),
    )
    client = TestClient(app)
    try:
        response = client.post("/api/v1/foc-demo/reasoning")
        refreshed = client.get("/api/v1/foc-demo")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["source"] == "persisted_model"
    assert response.json()["decisions"][0]["id"] == "cold-plate"
    assert repository.reasoning_path.is_file()
    assert refreshed.json()["design"]["source"] == "persisted_model"
