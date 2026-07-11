"""叶脉方向自动替换与仿真接口演示。

暂不调用真实 ANSYS；使用 LumpedSimulationBackend 验证编排协议。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.models.schema import LeafVeinParams
from core.engine.optimizer import OptimizationWeights, optimize_leaf_direction
from core.engine.simulation import LumpedSimulationBackend, SimulationContext


def main():
    base = LeafVeinParams(
        vein_archetype="fractal_tree",
        trunk_count=2,
        branch_levels=4,
        branch_angle=35.0,
        branch_ratio=0.68,
        width_trunk=2.4,
        width_tip=0.35,
        length_scale=40.0,
        channel_depth=0.25,
        density_gradient=0.30,
        tortuosity=1.35,
        symmetry=0.92,
        porosity=0.35,
        boundary_shape="rect",
        inlet_pos=0.5,
        outlet_pos=0.5,
        flow_direction_deg=90.0,
        cooling_medium="liquid",
    )
    context = SimulationContext(
        power_w=28.0,
        t_ambient_c=25.0,
        t_limit_c=80.0,
        material="AlSi10Mg",
        interface_r=0.18,
        source_model_path="organizer-model-placeholder.step",
    )
    result = optimize_leaf_direction(
        base,
        context=context,
        backend=LumpedSimulationBackend(),
        flow_directions_deg=[0, 45, 90, 135, 180, 225, 270, 315],
        branch_angles=[28, 35, 42],
        weights=OptimizationWeights(thermal=0.65, aesthetics=0.25, mass=0.10),
        top_k=5,
    )
    print("Leaf direction optimization demo")
    print("searched:", result["searched_candidates"])
    best = result["best"]
    print("best direction:", best["params"]["flow_direction_deg"], "deg")
    print("best branch angle:", best["params"]["branch_angle"], "deg")
    print("estimated hotspot:", best["simulation"]["t_hotspot_c"], "C")
    print("aesthetics:", best["aesthetics_score"], "| total:", best["total_score"])
    print("handoff:", result["handoff"]["simulation_interface"])

    out = ROOT / "data" / "leaf_optimizer_demo.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("written:", out)


if __name__ == "__main__":
    main()
