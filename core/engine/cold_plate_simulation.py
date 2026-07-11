"""冷板仿真后端抽象与两个实现。

本模块回答“仿真结果如何反哺优化”：优化器给出 ColdPlateParams，仿真后端返回
ColdPlateObjectives（热点温度 / 压降 / 质量 / 应力）。后续 evaluate_objectives()
把这些指标转成约束惩罚与加权成本，交给排序器。

============================================================================
仿真输出 -> ColdPlateObjectives 字段映射表
============================================================================
| ColdPlateObjectives 字段 | 含义                  | 来源 / 单位        |
|---------------------------|-----------------------|--------------------|
| max_temperature_c         | 最高温度              | K 或 C，统一为 °C  |
| pressure_drop_pa          | 流阻 / 进出口压降     | Pa                 |
| mass_g                    | 结构质量              | g                  |
| max_stress_mpa            | 最大等效应力          | MPa（可缺省）      |

ANSYS 导出 JSON 约定（ColdPlateExternalBackend 使用）：
{
  "max_temperature_c": 76.4,
  "pressure_drop_pa": 1280.0,
  "mass_g": 184.5,
  "max_stress_mpa": 91.2
}
也可嵌套在 {"result": {...}} 结构中，脚本会自动下钻。
============================================================================
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict

from ..models.cold_plate import ColdPlateParams
from .cold_plate_optimization import ColdPlateObjectives

# 材料密度（g/mm^3）。AlSi10Mg 为常见增材制造铝合金。
_MATERIAL_DENSITY_G_PER_MM3 = {
    "AlSi10Mg": 0.00267,
    "Al6061": 0.00270,
    "Cu": 0.00896,
    "Steel": 0.00785,
}


class ColdPlateSimulationBackend(ABC):
    """冷板仿真适配器必须实现的最小契约。"""

    name = "abstract"

    @abstractmethod
    def evaluate(self, params: ColdPlateParams, context: Any) -> ColdPlateObjectives:
        raise NotImplementedError


class ColdPlateLumpedBackend(ColdPlateSimulationBackend):
    """开发期解析估算器（离线 oracle）。

    不调用真实 CFD/FEA，仅用几何与一阶传热/流阻关系给出物理合理的趋势：
    - 质量：三层实体体积 + 流道隔墙体积，乘材料密度；
    - 压降：按平行微通道达西摩擦 + 进出口集流损失估算；
    - 热点温度：换热面积越大（通道越密、流道层越厚）、热导越好，温度越低；
    - 应力：占位，由压降与薄壁耦合给出粗略上界（可为 None）。

    用途：在无 ANSYS 环境时跑通“参数 -> 几何 -> 指标 -> 排序”闭环，
    并验证优化器确实能区分更优结构。真实仿真接入后由 ColdPlateExternalBackend 替代。
    """

    name = "lumped_estimator"

    def __init__(self, material: str = "AlSi10Mg", flow_rate_lpm: float = 1.0):
        self.material = material
        self.flow_rate_lpm = flow_rate_lpm
        self.density = _MATERIAL_DENSITY_G_PER_MM3.get(material, 0.00267)

    def evaluate(self, params: ColdPlateParams, context: Any = None) -> ColdPlateObjectives:
        errors = params.validate()
        if errors:
            raise ValueError("; ".join(errors))

        # ---- 几何体积与质量 -------------------------------------------------
        base_volume = params.outer_width_x * params.outer_length_y * params.t_layer1
        cover_volume = params.outer_width_x * params.outer_length_y * params.t_layer3
        frame_area = (
            params.outer_width_x * params.outer_length_y
            - params.flow_width_x * params.flow_length_y
        )
        layer2_frame_volume = frame_area * params.t_layer2
        channel_wall_volume = (
            (params.n_channels - 1) * params.channel_gap
            * params.straight_channel_length * params.t_layer2
        )
        solid_volume = (
            base_volume + cover_volume + layer2_frame_volume + channel_wall_volume
        )
        mass_g = solid_volume * self.density

        # ---- 流阻（平行微通道近似） ----------------------------------------
        n_ch = float(params.n_channels)
        channel_area = params.channel_width * params.t_layer2  # 单通道横截面积 mm^2
        hydraulic_d = 2.0 * channel_area / (params.channel_width + params.t_layer2)
        total_flow_mm3_s = self.flow_rate_lpm * 1e6 / 60.0  # L/min -> mm^3/s
        velocity = total_flow_mm3_s / max(n_ch * channel_area, 1e-9)  # mm/s
        L = params.straight_channel_length
        # 矩形微通道摩擦因子（简化，层流近似 f·Re ≈ 14.2）
        re = max(velocity * hydraulic_d / 1.0, 1e-6)  # 假设运动粘度 ~1 mm^2/s 量级
        friction = 14.2 / re
        friction_drop = friction * (L / hydraulic_d) * 0.5 * 1.2e-9 * velocity ** 2  # 粗略 Pa 量级
        manifold_loss = 1.5 * 0.5 * 1.2e-9 * velocity ** 2
        pressure_drop_pa = max(n_ch, 1e-9) * (friction_drop + manifold_loss)

        # ---- 热点温度（集总热阻近似） --------------------------------------
        # 湿周换热面积 ~ 通道数 × 长度 × (宽 + 2×深)；面积越大越凉。
        wetted_perimeter = params.channel_width + 2.0 * params.t_layer2
        heat_transfer_area = n_ch * params.straight_channel_length * wetted_perimeter  # mm^2
        # 对流/导热增益：面积越大、流道层越厚（导热路径越短）越凉。
        conduction_gain = params.t_layer2 / max(params.t_layer1 + params.t_layer2, 1e-6)
        cooling_power = heat_transfer_area * (1.0 + 2.0 * conduction_gain)
        power_w = getattr(context, "power_w", 28.0) if context is not None else 28.0
        t_ambient = getattr(context, "t_ambient_c", 25.0) if context is not None else 25.0
        # 温升与功率成正比、与冷却能力成反比。
        delta_t = power_w * 1000.0 / max(cooling_power, 1e-6)
        max_temperature_c = t_ambient + delta_t

        # ---- 应力（占位上界） ---------------------------------------------
        # 薄壁 + 高压降下更易失效；给出粗略上界，真实值由 FEA 提供。
        max_stress_mpa = min(0.05 * pressure_drop_pa, 200.0) if pressure_drop_pa else None

        return ColdPlateObjectives(
            max_temperature_c=round(max_temperature_c, 3),
            pressure_drop_pa=round(pressure_drop_pa, 3),
            mass_g=round(mass_g, 4),
            max_stress_mpa=round(max_stress_mpa, 3) if max_stress_mpa is not None else None,
        )


class ColdPlateExternalBackend(ColdPlateSimulationBackend):
    """读取 ANSYS（Fluent/Mechanical）导出的结果 JSON -> ColdPlateObjectives。

    适用场景：在已安装授权的目标机上，SpaceClaim 无头生成 STEP -> 网格 ->
    Fluent/Mechanical 求解 -> 导出结果 JSON，再回灌本后端。本机未安装/未授权
    ANSYS 时不会调用此后端。
    """

    name = "external_simulation"

    def __init__(self, results_path: str = ""):
        self.results_path = results_path

    def evaluate(self, params: ColdPlateParams, context: Any = None) -> ColdPlateObjectives:
        path = self.results_path
        if not path:
            raise ValueError("ColdPlateExternalBackend 需要 results_path（ANSYS 结果 JSON）")
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        # 允许 {"result": {...}} 嵌套结构
        if "result" in data and isinstance(data["result"], dict):
            data = data["result"]
        required = ("max_temperature_c", "pressure_drop_pa", "mass_g")
        missing = [k for k in required if k not in data]
        if missing:
            raise ValueError("ANSYS 结果 JSON 缺少字段: " + ", ".join(missing))
        return ColdPlateObjectives(
            max_temperature_c=float(data["max_temperature_c"]),
            pressure_drop_pa=float(data["pressure_drop_pa"]),
            mass_g=float(data["mass_g"]),
            max_stress_mpa=float(data["max_stress_mpa"]) if "max_stress_mpa" in data else None,
        )
