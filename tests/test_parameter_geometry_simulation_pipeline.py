from __future__ import annotations

from dataclasses import asdict

import pytest
from fastapi.testclient import TestClient

from core.api.app import app
from core.engine.generator import generate
from core.engine.simulation import LumpedSimulationBackend, SimulationContext
from core.models.schema import ChannelParams, LeafVeinParams, from_dict


def test_leaf_structure_parameter_changes_geometry_and_simulation():
    base = LeafVeinParams(branch_levels=2, cooling_medium="air")
    edited = LeafVeinParams(branch_levels=5, cooling_medium="air")

    base_svg, base_stats = generate(base)
    edited_svg, edited_stats = generate(edited)
    backend = LumpedSimulationBackend()
    context = SimulationContext(power_w=28.0, t_ambient_c=25.0, t_limit_c=80.0)
    base_result = backend.evaluate_candidate(base, context)
    edited_result = backend.evaluate_candidate(edited, context)

    assert base_svg != edited_svg
    assert edited_stats.eff_area_mm2 > base_stats.eff_area_mm2
    assert edited_stats.material_vol_mm3 > base_stats.material_vol_mm3
    assert edited_result.t_hotspot_c < base_result.t_hotspot_c
    assert edited_result.mass_g > base_result.mass_g


def test_channel_structure_parameter_changes_geometry_and_simulation():
    base = ChannelParams(channel_pattern="pinfin", channel_count=16, cooling_medium="air")
    edited = ChannelParams(channel_pattern="pinfin", channel_count=64, cooling_medium="air")

    base_svg, base_stats = generate(base)
    edited_svg, edited_stats = generate(edited)
    backend = LumpedSimulationBackend()
    context = SimulationContext(power_w=28.0, t_ambient_c=25.0, t_limit_c=80.0)
    base_result = backend.evaluate_candidate(base, context)
    edited_result = backend.evaluate_candidate(edited, context)

    assert base_svg.count("<circle") == 16
    assert edited_svg.count("<circle") == 64
    assert edited_stats.eff_area_mm2 > base_stats.eff_area_mm2
    assert edited_stats.material_vol_mm3 > base_stats.material_vol_mm3
    assert edited_result.t_hotspot_c < base_result.t_hotspot_c
    assert edited_result.mass_g > base_result.mass_g


def test_flow_direction_changes_svg_but_not_scalar_geometry_without_flow_context():
    direction_0 = LeafVeinParams(flow_direction_deg=0.0)
    direction_90 = LeafVeinParams(flow_direction_deg=90.0)

    svg_0, stats_0 = generate(direction_0)
    svg_90, stats_90 = generate(direction_90)
    backend = LumpedSimulationBackend()
    context = SimulationContext(preferred_flow_direction_deg=None)

    assert svg_0 != svg_90
    assert asdict(stats_0) == pytest.approx(asdict(stats_90))
    assert backend.evaluate_candidate(direction_0, context).t_hotspot_c == backend.evaluate_candidate(
        direction_90, context
    ).t_hotspot_c


def test_leaf_optimization_api_passes_preferred_direction_into_simulation():
    client = TestClient(app)
    response = client.post(
        "/optimize/leaf-direction",
        json={
            "base_params": {
                "structure_type": "leaf_vein",
                "branch_levels": 4,
                "branch_angle": 35.0,
            },
            "flow_directions_deg": [0, 90, 180],
            "preferred_flow_direction_deg": 90,
            "aesthetic_weight": 0.0,
            "thermal_weight": 1.0,
            "mass_weight": 0.0,
            "top_k": 3,
        },
    )

    assert response.status_code == 200
    ranking = response.json()["ranking"]
    by_direction = {item["params"]["flow_direction_deg"]: item for item in ranking}

    assert by_direction[90.0]["simulation"]["result"]["direction_penalty_c"] == 0.0
    assert by_direction[0.0]["simulation"]["result"]["direction_penalty_c"] > 0.0
    assert by_direction[180.0]["simulation"]["result"]["direction_penalty_c"] > 0.0
    for item in ranking:
        assert item["simulation"]["result"]["t_hotspot_c"] == item["simulation"]["t_hotspot_c"]
    assert response.json()["best"]["params"]["flow_direction_deg"] == 90.0


def test_api_parameter_edit_regenerates_geometry_before_evaluation():
    client = TestClient(app)
    base_params = {
        "structure_type": "leaf_vein",
        "branch_levels": 2,
        "length_scale": 60.0,
        "cooling_medium": "air",
    }
    edited_params = {**base_params, "branch_levels": 5}

    base_geometry = client.post("/generate", json={"params": base_params})
    edited_geometry = client.post("/generate", json={"params": edited_params})
    base_simulation = client.post("/evaluate", json={"params": base_params})
    edited_simulation = client.post("/evaluate", json={"params": edited_params})

    assert base_geometry.status_code == 200
    assert edited_geometry.status_code == 200
    assert base_simulation.status_code == 200
    assert edited_simulation.status_code == 200
    assert edited_geometry.json()["svg"] != base_geometry.json()["svg"]
    assert edited_geometry.json()["geometry"]["eff_area_mm2"] > base_geometry.json()["geometry"]["eff_area_mm2"]
    assert edited_simulation.json()["t_hotspot_c"] < base_simulation.json()["t_hotspot_c"]


def test_from_dict_edit_is_applied_to_generated_model():
    params = from_dict(
        {
            "structure_type": "channel",
            "channel_pattern": "serpentine",
            "serpentine_turns": 8,
            "channel_width": 1.4,
            "channel_height": 3.5,
        }
    )
    svg, stats = generate(params)

    assert params.channel_pattern == "serpentine"
    assert params.serpentine_turns == 8
    assert "serpentine channel" in svg
    assert stats.eff_area_mm2 > stats.base_area_mm2
