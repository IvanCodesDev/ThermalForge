"""
ThermalForge 第一轮 Happy Path 演示

串起黑客松最小闭环（对齐动效 5 步）：
  1) 输入关节工况（热源功率、介质、目标）
  2) 生成三种候选结构（平板基线 / 叶脉热桥 / pin-fin 阵列）
  3) 热路模型评估每种结构（T_hotspot / time-to-limit / 质量）
  4) 相对基线算收益（PDF §9.4 三指标）
  5) 相似度匹配：从种子库拉最相近案例

运行：venv python scripts/demo_pipeline.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.models.schema import LeafVeinParams, ChannelParams, FlatBaselineParams
from core.engine.generator import generate
from core.engine.thermal import evaluate, compare
from core.engine.matcher import Library

DATA = ROOT / "data"


def fmt_ttl(s):
    return "稳态不越限" if s < 0 else f"{s}s"


def main():
    print("=" * 68)
    print("ThermalForge · 关节热管理外壳优化 · 第一轮 Happy Path")
    print("=" * 68)

    # ---- Step 1: 工况 ----
    P, T_amb, T_lim, medium = 28.0, 25.0, 80.0, "air"
    print(f"\n[Step1] 工况: 持续热源 {P}W  环境 {T_amb}℃  降额阈值 {T_lim}℃  介质 {medium}")
    print("        场景: 机器人膝关节电机端部持续负载，弱气流，重量敏感")

    # ---- Step 2 生成 + Step 3 评估 ----
    candidates = {
        "平板基线": FlatBaselineParams(length_scale=80, channel_depth=3, cooling_medium=medium),
        "叶脉热桥": LeafVeinParams(branch_levels=5, trunk_count=3, branch_angle=34,
                                   length_scale=80, boundary_shape="circle", cooling_medium=medium),
        "pin-fin阵列": ChannelParams(channel_pattern="pinfin", channel_count=64, channel_width=1.4,
                                     channel_height=8, length_scale=80, cooling_medium=medium),
    }
    print("\n[Step2/3] 生成结构 + 热路评估:")
    results = {}
    for name, params in candidates.items():
        svg, stats = generate(params)
        res = evaluate(stats, power_w=P, t_ambient_c=T_amb, t_limit_c=T_lim,
                       medium=medium, structure_type=params.structure_type)
        results[name] = res
        print(f"  - {name:<10} T_hotspot={res.t_hotspot_c:>6.1f}℃  "
              f"time_to_limit={fmt_ttl(res.time_to_limit_s):>12}  质量={res.mass_g:>7.1f}g  "
              f"R_total={res.r_total}")

    # ---- Step 4 收益对比 ----
    base = results["平板基线"]
    print("\n[Step4] 相对平板基线收益 (PDF §9.4 三指标):")
    for name in ("叶脉热桥", "pin-fin阵列"):
        g = compare(base, results[name])
        ttl = "∞(不越限)" if g["time_to_limit_gain_pct"] == float("inf") else f"{g['time_to_limit_gain_pct']}%"
        print(f"  - {name:<10} 降温 {g['delta_t_hotspot_c']:>5}℃  "
              f"到阈值时间 {ttl:>10}  增重 {g['delta_mass_g']:>6}g  "
              f"单位重量收益×{g['per_mass_gain_ratio']}")

    # ---- Step 5 相似度匹配 ----
    print("\n[Step5] 相似度匹配（从种子库检索最相近案例）:")
    lib = Library.load(DATA / "seed_library.json")
    if not lib.cases:
        print("  ⚠ 种子库为空，请先运行 scripts/build_library.py")
    else:
        query = LeafVeinParams(branch_levels=5, trunk_count=1, branch_angle=30,
                               length_scale=68, boundary_shape="circle", cooling_medium="air")
        hits = lib.match(query.to_vector(), structure_type="leaf_vein", medium="air", top_k=3)
        for h in hits:
            print(f"  - [{h['case_id']}] sim={h['similarity']}  {h['note']}  "
                  f"(T={h['metrics']['t_hotspot_c']}℃)")

    print("\n" + "=" * 68)
    winner = min(results.items(), key=lambda kv: kv[1].t_hotspot_c)
    print(f"结论: 该工况下最低热点温度 = {winner[0]} ({winner[1].t_hotspot_c}℃)")
    print("Happy Path 跑通 ✅  结构 SVG 已存 data/，可接前端 3D/图形展示。")
    print("=" * 68)


if __name__ == "__main__":
    main()
