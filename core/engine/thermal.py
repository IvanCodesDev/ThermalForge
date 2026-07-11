"""
简化热路模型（PDF「可信的简化版」路线）

不做 CFD，用集总热阻网络 + 一阶集总热容，给出可对比、物理量纲正确的估算：

热路径（对齐 PDF §2.2 完整热阻链）：
  热源(结) --R_interface--> 壳体/结构 --R_spread--> 换热面 --R_conv--> 空气/液体

  T_hotspot(稳态) = T_ambient + P * R_total
  瞬态一阶：T(t) = T_amb + P*R_total * (1 - exp(-t / tau)),  tau = R_total * C_th
  到阈值时间 time_to_limit = -tau * ln(1 - (T_limit - T_amb)/(P*R_total))

材料默认 AlSi10Mg（PDF §3.3 推荐）：
  导热率 k≈150 W/mK（热处理后），密度 ρ=2670 kg/m³，比热 c=900 J/kgK

对比对象：flat / leaf_vein / pin-fin，用相同 P、T_amb、介质，输出：
  T_hotspot、time_to_limit、质量、单位重量换热收益（PDF §9.4 三指标）
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Dict, Any

from .generator import GeometryStats

# 材料属性
MATERIALS = {
    "AlSi10Mg": {"k": 150.0, "rho": 2670.0, "c": 900.0},
    "Cu":       {"k": 385.0, "rho": 8960.0, "c": 385.0},
    "Graphite": {"k": 400.0, "rho": 2200.0, "c": 710.0},
}

# 介质对流换热系数 h (W/m²K) 的典型量级
MEDIUM_H = {
    "air": 45.0,          # 关节运动气流下的弱强制对流
    "liquid": 900.0,      # 液冷
    "phase_change": 1500.0,
    "heat_pipe": 1200.0,
    "forced_air": 250.0,  # 螺旋桨洗流 / 机载风扇强对流（无人机动力典型）
}


@dataclass
class ThermalResult:
    structure_type: str
    material: str
    medium: str
    power_w: float
    t_ambient_c: float
    t_limit_c: float
    r_interface: float
    r_spread: float
    r_conv: float
    r_total: float
    t_hotspot_c: float
    mass_g: float
    thermal_capacitance_j_k: float
    tau_s: float
    time_to_limit_s: float          # -1 表示稳态温度低于阈值（永不越限，最好情况）
    per_mass_gain: float            # 单位质量换热收益（相对指标）

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def evaluate(stats: GeometryStats,
             power_w: float = 40.0,
             t_ambient_c: float = 25.0,
             t_limit_c: float = 80.0,
             material: str = "AlSi10Mg",
             medium: str = "air",
             interface_r: float = 0.35,
             structure_type: str = "structure") -> ThermalResult:
    """对单个结构做热评估。interface_r=热源到结构的接触热阻(K/W)，各结构相同以公平对比。"""
    mat = MATERIALS.get(material, MATERIALS["AlSi10Mg"])
    h = MEDIUM_H.get(medium, MEDIUM_H["air"])

    # 面积换算 mm² -> m²
    eff_area_m2 = max(stats.eff_area_mm2, 1.0) * 1e-6
    vol_m3 = max(stats.material_vol_mm3, 1.0) * 1e-9

    # R_conv：对流热阻 = 1/(h*A)。面积越大越小。
    r_conv = 1.0 / (h * eff_area_m2)

    # R_spread：扩散热阻，spread_factor 越大越小（叶脉最优）。
    # 基准扩散热阻按材料导热率与特征尺度粗估
    char_len_m = math.sqrt(stats.base_area_mm2) * 1e-3
    r_spread_base = char_len_m / (mat["k"] * eff_area_m2 + 1e-9)
    r_spread = r_spread_base * (1.2 - stats.spread_factor)  # spread_factor 高 → 系数低

    r_total = interface_r + r_spread + r_conv

    # 稳态热点温度
    t_hotspot = t_ambient_c + power_w * r_total

    # 质量 & 热容
    mass_kg = vol_m3 * mat["rho"]
    mass_g = mass_kg * 1000.0
    c_th = mass_kg * mat["c"]  # J/K
    tau = r_total * c_th

    # 到阈值时间
    dt_limit = t_limit_c - t_ambient_c
    steady_rise = power_w * r_total
    if steady_rise <= dt_limit:
        time_to_limit = -1.0  # 稳态都不越限
    else:
        ratio = 1.0 - dt_limit / steady_rise
        time_to_limit = -tau * math.log(max(ratio, 1e-9))

    # 单位质量换热收益：有效换热面积 / 质量（越大越划算）
    per_mass_gain = stats.eff_area_mm2 / max(mass_g, 1e-6)

    return ThermalResult(
        structure_type=structure_type,
        material=material,
        medium=medium,
        power_w=power_w,
        t_ambient_c=t_ambient_c,
        t_limit_c=t_limit_c,
        r_interface=round(interface_r, 4),
        r_spread=round(r_spread, 4),
        r_conv=round(r_conv, 4),
        r_total=round(r_total, 4),
        t_hotspot_c=round(t_hotspot, 2),
        mass_g=round(mass_g, 2),
        thermal_capacitance_j_k=round(c_th, 3),
        tau_s=round(tau, 2),
        time_to_limit_s=round(time_to_limit, 1),
        per_mass_gain=round(per_mass_gain, 3),
    )


def compare(baseline: ThermalResult, candidate: ThermalResult) -> Dict[str, Any]:
    """候选相对基线的收益（PDF §9.4 三指标）。"""
    d_temp = round(baseline.t_hotspot_c - candidate.t_hotspot_c, 2)  # 正=降温
    # time-to-limit 延长比例
    def _ttl(x):
        return x if x > 0 else float("inf")
    b_ttl, c_ttl = _ttl(baseline.time_to_limit_s), _ttl(candidate.time_to_limit_s)
    if math.isinf(c_ttl) and not math.isinf(b_ttl):
        ttl_gain = float("inf")
    elif math.isinf(b_ttl):
        ttl_gain = 0.0
    else:
        ttl_gain = round((c_ttl - b_ttl) / b_ttl * 100, 1)
    d_mass = round(candidate.mass_g - baseline.mass_g, 2)
    return {
        "delta_t_hotspot_c": d_temp,             # 热点温度下降 ℃
        "time_to_limit_gain_pct": ttl_gain,      # 到阈值时间延长 %
        "delta_mass_g": d_mass,                  # 增重 g
        "per_mass_gain_ratio": round(candidate.per_mass_gain / max(baseline.per_mass_gain, 1e-9), 2),
    }
