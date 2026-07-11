from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.services.foc_demo import (
    AssetNotFoundError,
    FocDemoRepository,
    redact_backend_output,
)


def _write_demo_output(path: Path, asset_dir: Path) -> None:
    (asset_dir / "rodin.glb").write_bytes(b"glTF-demo")
    (asset_dir / "bang.glb").write_bytes(b"glTF-parts")
    (asset_dir / "preview.webp").write_bytes(b"RIFF-preview")
    payload = {
        "generated_at": "2026-07-10T17:31:10+00:00",
        "scenario": "FOC 六轴协作机械臂肘关节热设计",
        "configured_models": {
            "text_model": "gpt-5.6-sol",
            "credentials_present": {"openai": True, "hyper3d": True},
        },
        "engineering_input": "48V PMSM，持续热耗散 120W，峰值 220W。",
        "confirmed_brief": {
            "device_type": "关节电机",
            "dimensions": {"length_mm": 160, "width_mm": 140, "height_mm": 110},
            "power_w": 120,
            "max_temp_c": 85,
            "ambient_temp_c": 35,
            "material": "铝6061",
            "manufacturing": "CNC",
            "max_weight_g": 850,
            "state": "confirmed",
        },
        "screening_evaluation": {
            "fidelity": "screening",
            "backend": "lumped_estimator",
            "not_cfd": True,
            "metrics": {"t_hotspot_c": 159.56, "r_total": 1.038, "mass_g": 4.4},
            "limitations": ["不是 CFD"],
        },
        "external_calls": {
            "gpt_5_6_sol": {"status": "success"},
            "hyper3d_rodin": {
                "status": "done",
                "response": {"uuid": "rodin-task", "jobs": {"subscription_key": "secret-sub"}},
                "local_assets": [
                    {"name": "base.glb", "local_path": "outputs/foc_robot_arm_assets/rodin.glb", "size_bytes": 9},
                    {"name": "preview.webp", "local_path": "outputs/foc_robot_arm_assets/preview.webp", "size_bytes": 12},
                ],
            },
            "hyper3d_bang": {
                "status": "done",
                "local_assets": [
                    {"name": "parts.glb", "local_path": "outputs/foc_robot_arm_assets/bang.glb", "size_bytes": 10}
                ],
            },
        },
        "bang_glb_structure": {"node_count": 4, "mesh_count": 3, "mesh_names": ["root.0", "root.1", "root.2"]},
        "disclaimers": ["概念网格不是可制造 CAD"],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_redact_backend_output_removes_credentials_and_signed_url_queries() -> None:
    raw = {
        "api_key": "sk-secret",
        "jobs": {"subscription_key": "sub-secret"},
        "download": {"url": "https://assets.example/model.glb?token=url-secret&expires=1"},
        "model": "gpt-5.6-sol",
    }

    safe = redact_backend_output(raw)
    serialized = json.dumps(safe)

    assert "sk-secret" not in serialized
    assert "sub-secret" not in serialized
    assert "url-secret" not in serialized
    assert safe["download"]["url"] == "https://assets.example/model.glb"
    assert safe["model"] == "gpt-5.6-sol"


def test_repository_builds_auditable_snapshot_with_real_local_assets(tmp_path: Path) -> None:
    output = tmp_path / "backend.json"
    assets = tmp_path / "assets"
    assets.mkdir()
    _write_demo_output(output, assets)
    repository = FocDemoRepository(output_path=output, asset_dir=assets)

    snapshot = repository.snapshot()

    assert snapshot.run_id == "foc-arm-demo"
    assert snapshot.scenario.startswith("FOC")
    assert snapshot.thermal.metrics["t_hotspot_c"] == 159.56
    assert snapshot.thermal.not_cfd is True
    assert {asset.id for asset in snapshot.assets} == {"rodin-model", "bang-model", "rodin-preview"}
    assert next(asset for asset in snapshot.assets if asset.id == "bang-model").url.endswith("/bang.glb")
    assert snapshot.mesh_structure.mesh_count == 3
    assert [stage.status for stage in snapshot.stages].count("done") >= 5
    assert snapshot.design.decisions
    assert snapshot.design.heat_paths
    assert snapshot.limitations


def test_repository_uses_persisted_model_reasoning_when_available(tmp_path: Path) -> None:
    output = tmp_path / "backend.json"
    assets = tmp_path / "assets"
    reasoning = tmp_path / "reasoning.json"
    assets.mkdir()
    _write_demo_output(output, assets)
    reasoning.write_text(
        json.dumps(
            {
                "architecture": "双热源、双路径、被动优先并预留液冷",
                "heat_paths": [
                    {
                        "name": "FOC 功率级",
                        "route": ["MOSFET", "导热垫", "冷板", "铝壳"],
                        "why": "缩短高热流密度器件的界面路径",
                        "evidence": ["持续 120W", "85°C 上限"],
                        "validation": "双热源热网络与 CFD",
                    }
                ],
                "decisions": [
                    {
                        "id": "liquid-ready",
                        "title": "预留环形液冷流道",
                        "choice": "首版被动散热，接口兼容液冷升级",
                        "why": "筛选级热点已超限",
                        "tradeoff": "增加密封与加工复杂度",
                        "evidence": ["159.56°C > 85°C"],
                        "validation": "流阻、泄漏与热循环",
                        "confidence": "high",
                    }
                ],
                "risks": ["自然对流不足"],
                "validation_tasks": ["建立电机与 MOSFET 双热源模型"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    repository = FocDemoRepository(output_path=output, asset_dir=assets, reasoning_path=reasoning)

    snapshot = repository.snapshot()

    assert snapshot.design.architecture.startswith("双热源")
    assert snapshot.design.decisions[0].id == "liquid-ready"


def test_repository_rejects_path_traversal_and_unknown_assets(tmp_path: Path) -> None:
    output = tmp_path / "backend.json"
    assets = tmp_path / "assets"
    assets.mkdir()
    _write_demo_output(output, assets)
    repository = FocDemoRepository(output_path=output, asset_dir=assets)

    with pytest.raises(AssetNotFoundError):
        repository.resolve_asset("../backend.json")
    with pytest.raises(AssetNotFoundError):
        repository.resolve_asset("not-listed.glb")


def test_repository_enforces_fidelity_boundaries_over_backend_claims(tmp_path: Path) -> None:
    output = tmp_path / "backend.json"
    assets = tmp_path / "assets"
    assets.mkdir()
    _write_demo_output(output, assets)
    payload = json.loads(output.read_text(encoding="utf-8"))
    payload["screening_evaluation"]["not_cfd"] = False
    payload["bang_glb_structure"]["manufacturable_cad"] = True
    output.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    snapshot = FocDemoRepository(output_path=output, asset_dir=assets).snapshot()

    assert snapshot.thermal.not_cfd is True
    assert snapshot.mesh_structure.manufacturable_cad is False


def test_repository_redacts_persisted_reasoning_before_validation(tmp_path: Path) -> None:
    output = tmp_path / "backend.json"
    assets = tmp_path / "assets"
    reasoning = tmp_path / "reasoning.json"
    assets.mkdir()
    _write_demo_output(output, assets)
    reasoning.write_text(
        json.dumps(
            {
                "architecture": "https://design.example/architecture?token=url-secret&expires=1",
                "components": [
                    {
                        "api_key": "sk-reasoning-secret",
                        "url": "https://design.example/component?signature=component-secret",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    snapshot = FocDemoRepository(
        output_path=output,
        asset_dir=assets,
        reasoning_path=reasoning,
    ).snapshot()
    serialized = json.dumps(snapshot.design.model_dump(mode="json"))

    assert snapshot.design.architecture == "https://design.example/architecture"
    assert "sk-reasoning-secret" not in serialized
    assert "component-secret" not in serialized


def test_repository_does_not_allow_reasoning_to_override_source(tmp_path: Path) -> None:
    output = tmp_path / "backend.json"
    assets = tmp_path / "assets"
    reasoning = tmp_path / "reasoning.json"
    assets.mkdir()
    _write_demo_output(output, assets)
    reasoning.write_text(
        json.dumps({"source": "untrusted-override", "architecture": "双热源架构"}, ensure_ascii=False),
        encoding="utf-8",
    )

    snapshot = FocDemoRepository(
        output_path=output,
        asset_dir=assets,
        reasoning_path=reasoning,
    ).snapshot()

    assert snapshot.design.source == "persisted_model"
