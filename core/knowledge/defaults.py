"""默认目录（特性一/二共享默认数据源）。

落实 OQ1（默认 BLDC 电机 + 默认热耗）、OQ3（默认翅片/分瓣角由 handoff
编译器使用，见 `core/services/spaceclaim_handoff.py`）、OQ5（缺字段用知识库
默认材质表补）。所有数值与 `docs/agent-system/examples/spaceclaim-handoff.v1.json`
对齐。
"""
from __future__ import annotations

from typing import Any, ClassVar

from core.knowledge.templates import MotorDatasheetTemplate

#: MaterialProperties 的 8 个显式字段（顺序即契约字段顺序）。
MATERIAL_PROPERTY_KEYS: tuple[str, ...] = (
    "density_kg_m3",
    "thermal_conductivity_w_mk",
    "specific_heat_j_kgk",
    "coefficient_thermal_expansion_1_k",
    "youngs_modulus_pa",
    "poissons_ratio",
    "yield_strength_pa",
    "ultimate_tensile_strength_pa",
)

DEFAULT_BLDC_MOTOR: dict[str, Any] = {
    "motor_type": "BLDC",
    "rated_power_w": 50.0,
    "rated_voltage_v": 48.0,
    "rated_speed_rpm": 3000.0,
    "winding_resistance_ohm": 0.5,
    "efficiency": 0.85,
    "thermal": {"heat_loss_fraction": 0.15, "max_winding_temp_c": 120.0},
}

DEFAULT_MATERIALS: dict[str, dict[str, Any]] = {
    "al": {
        "material_id": "al",
        "name": "Aluminum",
        "density_kg_m3": 2700.0,
        "thermal_conductivity_w_mk": 167.0,
        "specific_heat_j_kgk": 896.0,
        "coefficient_thermal_expansion_1_k": 2.3e-5,
        "youngs_modulus_pa": 69e9,
        "poissons_ratio": 0.33,
        "yield_strength_pa": 276e6,
        "ultimate_tensile_strength_pa": 310e6,
    },
    "steel": {
        "material_id": "steel",
        "name": "Steel",
        "density_kg_m3": 7850.0,
        "thermal_conductivity_w_mk": 50.0,
        "specific_heat_j_kgk": 490.0,
        "coefficient_thermal_expansion_1_k": 1.2e-5,
        "youngs_modulus_pa": 200e9,
        "poissons_ratio": 0.30,
        "yield_strength_pa": 250e6,
        "ultimate_tensile_strength_pa": 460e6,
    },
}


class BldcDefaults:
    """默认 BLDC 目录与默认材质表的静态访问入口。"""

    DEFAULT_BLDC_MOTOR: ClassVar[dict[str, Any]] = DEFAULT_BLDC_MOTOR
    DEFAULT_MATERIALS: ClassVar[dict[str, dict[str, Any]]] = DEFAULT_MATERIALS
    DEFAULT_THERMAL_LOSS_FRACTION: ClassVar[float] = 0.15

    @staticmethod
    def default_bldc_motor_template() -> MotorDatasheetTemplate:
        """返回默认 BLDC 电机的数据手册模板实例。"""
        motor = DEFAULT_BLDC_MOTOR
        return MotorDatasheetTemplate(
            motor_type=motor["motor_type"],
            rated_power_w=float(motor["rated_power_w"]),
            rated_voltage_v=float(motor["rated_voltage_v"]),
            rated_speed_rpm=float(motor["rated_speed_rpm"]),
            winding_resistance_ohm=float(motor["winding_resistance_ohm"]),
            efficiency=float(motor["efficiency"]),
        )

    @staticmethod
    def default_material_properties(material_id: str) -> dict[str, float]:
        """返回指定材质的 8 字段字典（OQ5 补缺用）。

        Args:
            material_id: 材质标识，当前支持 ``"al"`` / ``"steel"``。

        Raises:
            KeyError: 当 material_id 不在默认材质表中时。
        """
        if material_id not in DEFAULT_MATERIALS:
            raise KeyError(f"未知材质 {material_id!r}，默认材质表仅含 {sorted(DEFAULT_MATERIALS)}")
        props = DEFAULT_MATERIALS[material_id]
        return {key: float(props[key]) for key in MATERIAL_PROPERTY_KEYS}

    @staticmethod
    def default_motor_thermal_load_w() -> float:
        """默认电机热耗 = 额定功率 × 热损比例 = 50 × 0.15 = 7.5 W（OQ1）。"""
        motor = DEFAULT_BLDC_MOTOR
        return float(motor["rated_power_w"]) * float(motor["thermal"]["heat_loss_fraction"])
