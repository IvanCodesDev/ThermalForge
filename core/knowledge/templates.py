"""知识库文档模板（特性二）。

纯 pydantic 模板类，复用项目既有 pydantic 体系；`extra="forbid"` 保证
抽取结果只含已知字段。所有模板默认 `motor_type="BLDC"`（OQ2 裁定）。
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class _StrictModel(BaseModel):
    """本地严格模型：禁止额外字段，但不启用 strict 模式以兼容 None 默认值。"""

    model_config = ConfigDict(extra="forbid")


class MotorDatasheetTemplate(_StrictModel):
    """电机数据手册模板；默认 BLDC。"""

    motor_type: str = "BLDC"
    rated_power_w: float | None = None
    rated_voltage_v: float | None = None
    rated_speed_rpm: float | None = None
    winding_resistance_ohm: float | None = None
    efficiency: float | None = None


class RobotArmSpecTemplate(_StrictModel):
    """机械臂规格模板；默认 BLDC。"""

    motor_type: str = "BLDC"
    dof: int | None = None
    reach_mm: float | None = None
    payload_kg: float | None = None


class MaterialSpecTemplate(_StrictModel):
    """材料规格模板。"""

    name: str
    density_kg_m3: float | None = None
    thermal_conductivity_w_mk: float | None = None
    specific_heat_j_kgk: float | None = None
    youngs_modulus_pa: float | None = None
