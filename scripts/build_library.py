"""
构建种子案例库（预参数化 + 预计算热指标 + 预生成 SVG）

产出：
  data/seed_library.json    —— 匹配用（几何 constraint_vector + 指标 + device_context 意图上下文）
  data/leaf_vein/*.svg      —— 叶脉结构图
  data/channel/*.svg        —— 流道/pin-fin 结构图

每个库案例按 parameter-schema-v0.1.md §2.5 参数化入库：
  - params / constraint_vector（几何向量）：供 engine.matcher 几何相似度匹配 + /generate /evaluate
  - device_context（UserInput）：供参数中枢意图匹配（ParameterHub.match_user_to_library）
  - model_path / preview_img / perf_notes：展示用

运行：venv python scripts/build_library.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.models.schema import LeafVeinParams, ChannelParams, FlatBaselineParams
from core.models.user_input import UserInput
from core.engine.generator import generate
from core.engine.thermal import evaluate
from core.engine.matcher import Library

DATA = ROOT / "data"

# 种子案例：覆盖 关节热管理三大候选结构 × 典型工况
# (case_id, source, note, params, device_context)
SEEDS = [
    ("LV-001", "programmatic", "膝关节电机端部热扩散·气冷",
     LeafVeinParams(branch_levels=5, trunk_count=1, branch_angle=32, length_scale=70,
                    boundary_shape="circle", cooling_medium="air"),
     UserInput(device_type="关节电机", dimensions={"outer_dia_mm": 50, "inner_dia_mm": 20, "height_mm": 40},
               power_w=28.0, max_temp_c=80.0, material="铝6061", has_fan=False,
               max_weight_g=35.0, manufacturing="3D打印", ambient_temp_c=25.0)),

    ("LV-002", "programmatic", "髋关节大面积叶脉热桥·气冷",
     LeafVeinParams(branch_levels=4, trunk_count=3, branch_angle=40, length_scale=90,
                    boundary_shape="rect", cooling_medium="air"),
     UserInput(device_type="关节电机", dimensions={"length_mm": 90, "width_mm": 90, "height_mm": 50},
               power_w=45.0, max_temp_c=85.0, material="铝6061", has_fan=False,
               max_weight_g=120.0, manufacturing="3D打印", ambient_temp_c=25.0)),

    ("LV-003", "programmatic", "驱控板叶脉导热桥·液冷微通道",
     LeafVeinParams(branch_levels=5, trunk_count=2, branch_angle=28, length_scale=50,
                    channel_depth=2.0, boundary_shape="rect", cooling_medium="liquid"),
     UserInput(device_type="MOSFET/驱动器", dimensions={"length_mm": 50, "width_mm": 40, "height_mm": 30},
               power_w=35.0, max_temp_c=90.0, material="铜", has_fan=False,
               max_weight_g=80.0, manufacturing="CNC", ambient_temp_c=25.0)),

    ("PF-001", "programmatic", "MOSFET热点·pin-fin圆柱阵列·弱气流首选",
     ChannelParams(channel_pattern="pinfin", channel_count=49, channel_width=1.2,
                   channel_height=6, length_scale=45, boundary_shape="rect", cooling_medium="air"),
     UserInput(device_type="MOSFET/驱动器", dimensions={"length_mm": 45, "width_mm": 45, "height_mm": 30},
               power_w=30.0, max_temp_c=100.0, material="铝6061", has_fan=False,
               max_weight_g=40.0, manufacturing="3D打印", ambient_temp_c=25.0)),

    ("PF-002", "programmatic", "驱控板密集针阵·气冷",
     ChannelParams(channel_pattern="pinfin", channel_count=81, channel_width=1.0,
                   channel_height=5, length_scale=55, boundary_shape="rect", cooling_medium="air"),
     UserInput(device_type="MOSFET/驱动器", dimensions={"length_mm": 55, "width_mm": 55, "height_mm": 35},
               power_w=50.0, max_temp_c=95.0, material="铝6061", has_fan=True,
               max_weight_g=90.0, manufacturing="3D打印", ambient_temp_c=25.0)),

    ("CH-001", "programmatic", "膝关节保形蛇形流道·液冷",
     ChannelParams(channel_pattern="serpentine", serpentine_turns=8, channel_width=2.0,
                   channel_height=3, length_scale=60, boundary_shape="rect", cooling_medium="liquid"),
     UserInput(device_type="关节电机", dimensions={"length_mm": 60, "width_mm": 60, "height_mm": 40},
               power_w=40.0, max_temp_c=80.0, material="铝6061", has_fan=False,
               max_weight_g=60.0, manufacturing="3D打印", ambient_temp_c=25.0)),

    ("CH-002", "programmatic", "并行微通道冷板·液冷",
     ChannelParams(channel_pattern="parallel", channel_count=20, channel_width=1.0,
                   channel_height=4, length_scale=60, boundary_shape="rect", cooling_medium="liquid"),
     UserInput(device_type="Jetson/边缘计算盒", dimensions={"length_mm": 70, "width_mm": 50, "height_mm": 25},
               power_w=60.0, max_temp_c=85.0, material="铝6061", has_fan=True,
               max_weight_g=150.0, manufacturing="CNC", ambient_temp_c=25.0)),

    ("FB-000", "baseline", "平板铝块基线·对照组",
     FlatBaselineParams(length_scale=60, channel_depth=3, boundary_shape="rect", cooling_medium="air"),
     UserInput(device_type="关节电机", dimensions={"length_mm": 60, "width_mm": 60, "height_mm": 40},
               power_w=28.0, max_temp_c=80.0, material="铝6061", has_fan=False,
               max_weight_g=60.0, manufacturing="3D打印", ambient_temp_c=25.0)),

    ("DV-001", "programmatic", "无人机动力电机·pin-fin圆柱阵列·螺旋桨洗流强制风冷",
     ChannelParams(channel_pattern="pinfin", channel_count=120, channel_width=1.0,
                   channel_height=6, length_scale=60, boundary_shape="circle", cooling_medium="forced_air"),
     UserInput(device_type="无人机动力电机", dimensions={"outer_dia_mm": 60, "inner_dia_mm": 30, "height_mm": 40},
               power_w=150.0, max_temp_c=110.0, material="铝6061", has_fan=True,
               max_weight_g=200.0, manufacturing="CNC+3D打印", ambient_temp_c=40.0)),

    ("MD-001", "programmatic", "医疗激光模块·平行微通道冷板·液冷精密温控",
     ChannelParams(channel_pattern="parallel", channel_count=24, channel_width=1.0,
                   channel_height=4, length_scale=70, boundary_shape="rect", cooling_medium="liquid"),
     UserInput(device_type="医疗激光模块", dimensions={"length_mm": 70, "width_mm": 50, "height_mm": 25},
               power_w=300.0, max_temp_c=60.0, material="铝6061", has_fan=False,
               max_weight_g=500.0, manufacturing="CNC", ambient_temp_c=25.0)),
]


def main():
    (DATA / "leaf_vein").mkdir(parents=True, exist_ok=True)
    (DATA / "channel").mkdir(parents=True, exist_ok=True)
    lib = Library()

    for case_id, source, note, params, dc in SEEDS:
        svg, stats = generate(params)
        res = evaluate(stats, power_w=40.0, medium=params.cooling_medium,
                       structure_type=params.structure_type)
        st = params.structure_type
        subdir = "leaf_vein" if st == "leaf_vein" else "channel"
        svg_path = DATA / subdir / f"{case_id}.svg"
        svg_path.write_text(svg, encoding="utf-8")

        perf = (f"T_hotspot≈{res.t_hotspot_c}C / ttl≈{round(res.time_to_limit_s)}s / "
                f"mass≈{res.mass_g}g / eff_area≈{round(stats.eff_area_mm2)}mm²")

        lib.add({
            "case_id": case_id,
            "source": source,
            "note": note,
            "params": params.to_dict(),
            "geometry_vector": params.to_vector(),     # 几何向量（engine.matcher /match 用）
            "device_context": dc.to_dict(),            # 意图上下文（参数中枢 hub 用；intent constraint_vector 由 device_context 派生）
            "structure_type": st,
            "model_path": "",                           # 3D 模型待补（短期调库现成模型）
            "preview_img": str(svg_path.relative_to(ROOT)).replace("\\", "/"),
            "perf_notes": perf,
            "svg_path": str(svg_path.relative_to(ROOT)).replace("\\", "/"),
            "metrics": res.to_dict(),
        })
        print(f"[{case_id}] {note}")
        print(f"     T_hotspot={res.t_hotspot_c}C  ttl={res.time_to_limit_s}s  "
              f"mass={res.mass_g}g  eff_area={round(stats.eff_area_mm2)}mm2")

    lib.save(DATA / "seed_library.json")
    print(f"\nOK: {len(lib.cases)} cases -> {DATA/'seed_library.json'}")


if __name__ == "__main__":
    main()
