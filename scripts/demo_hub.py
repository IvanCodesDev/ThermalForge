"""
参数中枢 v0.2 · Happy Path 闭环演示

流程（对应 PRD 用户流程 + 参数中枢契约）：
  Step1  构造用户意图（上游输入层 UserInput）
  Step2  意图 → 约束向量（23 维用户意图空间）
  Step3  意图 ↔ 库案例 同空间匹配（match_user_to_library）
  Step4  意图 → 结构模板推荐（recommend_structure）
  Step5  生成 + 热路评估推荐结构，并与平板基线对比（PDF §9.4）

运行：venv python scripts/demo_hub.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.models.user_input import UserInput
from core.models.schema import from_dict
from core.parameter_hub import ParameterHub
from core.engine.generator import generate
from core.engine.thermal import evaluate, compare

DATA = ROOT / "data"


def main():
    print("=" * 68)
    print("ThermalForge · 参数中枢 v0.2 · 用户意图 → 库匹配 → 结构生成 闭环")
    print("=" * 68)

    # Step1 用户意图
    ui = UserInput(
        device_type="关节电机",
        dimensions={"outer_dia_mm": 50, "inner_dia_mm": 20, "height_mm": 40},
        power_w=28.0, max_temp_c=80.0, material="铝6061",
        has_fan=False, max_weight_g=35.0, manufacturing="3D打印", ambient_temp_c=25.0,
    )
    print(f"\n[Step1] 用户意图: {ui.device_type}  P={ui.power_w}W  "
          f"T_lim={ui.max_temp_c}℃  medium≈{ui.preferred_medium()}  "
          f"thermal_load={ui.thermal_load():.4f}W/mm³")

    # Step2 约束向量
    vec = ui.to_vector()
    print(f"[Step2] 约束向量维度 = {len(vec)}（与库案例同空间）")

    # Step3 库匹配
    hub = ParameterHub.from_library_json(DATA / "seed_library.json")
    print(f"\n[Step3] 库匹配 top-3（意图空间余弦）：")
    for e, sim in hub.match_user_to_library(ui, top_k=3):
        print(f"  - {e.case_id}  sim={sim:.4f}  {e.structure_type}  "
              f"介质={e.structure.get('cooling_medium')}  perf={e.perf_notes}")

    # Step4 结构推荐
    rec = hub.recommend_structure(ui)
    print(f"\n[Step4] 意图→结构模板推荐: {rec['structure_type']} "
          f"(pattern={rec.get('channel_pattern', rec.get('vein_archetype', '-'))}, "
          f"medium={rec.get('cooling_medium')})")

    # Step5 生成 + 评估 + 对比
    p = from_dict(rec)
    _, stats = generate(p)
    res = evaluate(stats, power_w=ui.power_w, t_ambient_c=ui.ambient_temp_c,
                   t_limit_c=ui.max_temp_c, material="AlSi10Mg",
                   medium=p.cooling_medium, structure_type=p.structure_type)
    print(f"\n[Step5] 推荐结构热评估: T_hotspot={res.t_hotspot_c}℃  "
          f"ttl={res.time_to_limit_s}s  mass={res.mass_g}g")

    d = ui.dimensions
    size = max(d.get("length_mm", 0.0), d.get("width_mm", 0.0), d.get("outer_dia_mm", 0.0)) or 60.0
    bp = from_dict({"structure_type": "flat", "length_scale": size, "channel_depth": 3,
                    "boundary_shape": "rect", "cooling_medium": "air"})
    _, bstats = generate(bp)
    bres = evaluate(bstats, power_w=ui.power_w, t_ambient_c=ui.ambient_temp_c,
                    t_limit_c=ui.max_temp_c, material="AlSi10Mg",
                    medium="air", structure_type="flat")
    gain = compare(bres, res)
    ttl_gain = "∞(不越限)" if gain["time_to_limit_gain_pct"] == float("inf") else f"{gain['time_to_limit_gain_pct']:.1f}%"
    print(f"        平板基线对比: 降温 {gain['delta_t_hotspot_c']:.1f}℃  "
          f"到阈值时间 {ttl_gain}  增重 {gain['delta_mass_g']:.1f}g  "
          f"单位重量收益 ×{gain['per_mass_gain_ratio']:.2f}")

    print("\n结论: 参数中枢契约跑通 ✅  用户输入 ↔ 库案例同空间匹配 ✅  意图→结构生成 ✅")
    print("=" * 68)


if __name__ == "__main__":
    main()
