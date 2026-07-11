from __future__ import annotations

import ast
import json
from pathlib import Path

from core.engine.cold_plate_optimization import (
    ColdPlateObjectives,
    build_cold_plate_candidates,
    evaluate_objectives,
    rank_simulation_results,
    run_cold_plate_loop,
    sample_cold_plate_candidates,
)
from core.engine.cold_plate_simulation import (
    ColdPlateExternalBackend,
    ColdPlateLumpedBackend,
)
from core.engine.spaceclaim import create_candidate_artifact, render_cold_plate_script
from core.models.cold_plate import ColdPlateParams


def test_reference_parameters_match_supplied_step_dimensions():
    params = ColdPlateParams()
    assert params.outer_width_x == 34.0
    assert params.outer_length_y == 52.0
    assert params.total_thickness == 3.25
    assert params.n_channels == 150
    assert params.straight_channel_length == 40.0


def test_parameter_change_produces_different_script_and_hash():
    base = ColdPlateParams(channel_width=0.10, channel_gap=0.10)
    edited = ColdPlateParams(channel_width=0.12, channel_gap=0.10)
    base_script = render_cold_plate_script(base, "base.stp")
    edited_script = render_cold_plate_script(edited, "edited.stp")

    assert base.parameter_hash() != edited.parameter_hash()
    assert base_script != edited_script
    assert "channel_width = 0.1" in base_script
    assert "channel_width = 0.12" in edited_script
    assert base.n_channels != edited.n_channels


def test_generated_script_compiles_and_uses_configured_api():
    params = ColdPlateParams()
    script = render_cold_plate_script(params, "out.stp", api_version="V252")
    # 生成脚本必须是合法 Python（SpaceClaim/IronPython 语法）
    ast.parse(script)
    assert "from SpaceClaim.Api.V252 import *" in script
    assert "ClearAll()" in script
    assert 'DocumentSave.Execute(output_step_path' in script
    # 反斜杠转换应使用正确的转义（生成脚本中的合法 Python 转义）
    assert 'output_step_path.replace("\\\\", "/")' in script


def test_default_script_reports_reference_dimensions():
    params = ColdPlateParams()
    script = render_cold_plate_script(params, "out.stp")
    assert "n_channels = 150" in script
    assert "Lx = margin_left + flow_width_x + margin_right" in script


def test_artifact_contains_reproducible_manifest(tmp_path: Path):
    params = ColdPlateParams()
    artifact = create_candidate_artifact(
        params,
        tmp_path,
        candidate_id="CP-TEST-001",
        source_model_path="0710.stp",
    )
    manifest = json.loads(Path(artifact.manifest_path).read_text(encoding="utf-8"))

    assert Path(artifact.script_path).exists()
    assert manifest["params_hash"] == params.parameter_hash()
    assert manifest["derived"]["n_channels"] == 150
    assert manifest["source_model_path"] == "0710.stp"
    assert manifest["status"] == "script_ready"
    assert artifact.api_version == "V252"


def test_search_space_builds_valid_candidate_matrix():
    base = ColdPlateParams()
    candidates = build_cold_plate_candidates(
        base,
        channel_widths=[0.08, 0.10],
        channel_gaps=[0.08, 0.10],
        layer2_thicknesses=[0.20, 0.25],
        manifold_lengths=[3.0, 4.0],
    )
    assert len(candidates) == 16
    assert all(not candidate.validate() for candidate in candidates)
    assert len({candidate.parameter_hash() for candidate in candidates}) == 16


def test_sample_search_produces_distinct_valid_candidates():
    base = ColdPlateParams()
    space = {
        "channel_width": [0.08, 0.14],
        "channel_gap": [0.06, 0.12],
        "t_layer2": [0.18, 0.35],
        "manifold_length": [3.0, 5.0],
    }
    samples = sample_cold_plate_candidates(base, space, n_samples=12, seed=3)
    assert len(samples) >= 6
    assert all(not s.validate() for s in samples)
    assert len({s.parameter_hash() for s in samples}) == len(samples)


def test_lumped_backend_monotonic_temperature_trend():
    backend = ColdPlateLumpedBackend()
    sparse = ColdPlateParams(channel_width=0.14, channel_gap=0.14, t_layer2=0.20)
    dense = ColdPlateParams(channel_width=0.08, channel_gap=0.08, t_layer2=0.30)
    t_sparse = backend.evaluate(sparse).max_temperature_c
    t_dense = backend.evaluate(dense).max_temperature_c
    # 通道更密、流道层更厚 -> 换热更好 -> 温度更低
    assert t_dense < t_sparse
    # 基本物质守恒：质量应随体积增长而增大
    assert backend.evaluate(dense).mass_g > 0.0


def test_simulation_feedback_prioritizes_feasible_candidate():
    feasible = evaluate_objectives(
        ColdPlateObjectives(
            max_temperature_c=72.0,
            pressure_drop_pa=900.0,
            mass_g=120.0,
            max_stress_mpa=100.0,
        )
    )
    infeasible = evaluate_objectives(
        ColdPlateObjectives(
            max_temperature_c=70.0,
            pressure_drop_pa=1500.0,
            mass_g=100.0,
            max_stress_mpa=90.0,
        )
    )
    ranked = rank_simulation_results(
        [
            {"candidate_id": "bad-pressure", "evaluation": infeasible},
            {"candidate_id": "feasible", "evaluation": feasible},
        ]
    )

    assert feasible["feasible"] is True
    assert infeasible["feasible"] is False
    assert ranked[0]["candidate_id"] == "feasible"


def test_external_backend_reads_ansys_result_json(tmp_path: Path):
    result = tmp_path / "ansys.json"
    result.write_text(
        json.dumps({
            "max_temperature_c": 76.4,
            "pressure_drop_pa": 1280.0,
            "mass_g": 184.5,
            "max_stress_mpa": 91.2,
        }),
        encoding="utf-8",
    )
    obj = ColdPlateExternalBackend(str(result)).evaluate(ColdPlateParams())
    assert obj.max_temperature_c == 76.4
    assert obj.pressure_drop_pa == 1280.0
    assert obj.mass_g == 184.5


def test_closed_loop_runs_offline_and_ranks(tmp_path: Path):
    base = ColdPlateParams()
    space = {
        "channel_width": [0.08, 0.12],
        "channel_gap": [0.08, 0.12],
        "t_layer2": [0.20, 0.30],
        "manifold_length": [3.0, 5.0],
    }
    backend = ColdPlateLumpedBackend()

    # 不传 candidate_builder，避免写入 tmp 之外；仅验证闭环评分与排序
    loop = run_cold_plate_loop(
        base=base,
        search_space=space,
        backend=backend,
        mode="grid",
        candidate_builder=None,
    )
    assert loop["count"] == 16  # 2*2*2*2 网格组合
    ranked = loop["ranked"]
    assert ranked[0]["evaluation"]["weighted_cost"] <= ranked[-1]["evaluation"]["weighted_cost"]

    # 最优候选的估算温度不高于最差候选
    best_obj = ranked[0]["objectives"]
    worst_obj = ranked[-1]["objectives"]
    assert best_obj["max_temperature_c"] <= worst_obj["max_temperature_c"]

