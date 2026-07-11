"""Deterministic engineering-budget model for the FOC elbow joint demo.

The loss figures in this module are allocated design budgets.  They are useful
for defining thermal loads and heat paths, but are not first-principles motor,
inverter, or drivetrain calculations.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class FocJointInput:
    """Declared operating point and thermal budgets for the demo joint."""

    axes: int = 6
    focus_joint: str = "J4 肘关节"
    motor_type: str = "PMSM"
    dc_bus_voltage_v: float = 48.0
    modulation: str = "SVPWM"
    current_loop_hz: int = 20_000
    continuous_loss_budget_w: float = 120.0
    peak_loss_budget_w: float = 220.0

    def __post_init__(self) -> None:
        if (
            isinstance(self.axes, bool)
            or not isinstance(self.axes, int)
            or self.axes <= 0
        ):
            raise ValueError("axes must be a positive integer")
        if not isfinite(self.dc_bus_voltage_v) or self.dc_bus_voltage_v <= 0:
            raise ValueError("dc_bus_voltage_v must be finite and greater than zero")
        if (
            isinstance(self.current_loop_hz, bool)
            or not isinstance(self.current_loop_hz, int)
            or self.current_loop_hz <= 0
        ):
            raise ValueError("current_loop_hz must be a positive integer")
        for field_name, value in (
            ("continuous_loss_budget_w", self.continuous_loss_budget_w),
            ("peak_loss_budget_w", self.peak_loss_budget_w),
        ):
            if not isfinite(value) or value < 0:
                raise ValueError(f"{field_name} must be finite and non-negative")
        if self.peak_loss_budget_w < self.continuous_loss_budget_w:
            raise ValueError(
                "peak_loss_budget_w must be greater than or equal to "
                "continuous_loss_budget_w"
            )


@dataclass(frozen=True)
class FocSystem:
    axes: int
    focus_joint: str
    motor_type: str


@dataclass(frozen=True)
class FocControl:
    dc_bus_voltage_v: float
    modulation: str
    current_loop_hz: int


@dataclass(frozen=True)
class FocLossSource:
    id: str
    group: str
    continuous_w: float
    peak_w: float
    heat_path: str


@dataclass(frozen=True)
class FocThermalTargets:
    mosfet_case_max_c: float = 85.0
    winding_max_c: float = 100.0


@dataclass(frozen=True)
class FocJointSimulationResult:
    system: FocSystem
    control: FocControl
    loss_sources: tuple[FocLossSource, ...]
    thermal_targets: FocThermalTargets
    total_continuous_loss_w: float
    total_peak_loss_w: float
    loss_model: str
    is_first_principles: bool
    assumptions: tuple[str, ...]
    validation_tasks: tuple[str, ...]

    @property
    def grouped_continuous_losses_w(self) -> dict[str, float]:
        grouped: dict[str, float] = {}
        for source in self.loss_sources:
            grouped[source.group] = grouped.get(source.group, 0.0) + source.continuous_w
        return grouped


# Shares sum to 1.0 and allocate the continuous budget by subsystem as
# PMSM 50%, inverter 30%, and drivetrain/control 20%.
_LOSS_ALLOCATIONS = (
    ("copper", "pmsm", 0.375, "绕组 -> 定子铁芯 -> 电机壳体 -> 关节外壳"),
    ("iron", "pmsm", 0.125, "定子铁芯 -> 电机壳体 -> 关节外壳"),
    (
        "mosfet_conduction",
        "foc_inverter",
        0.20,
        "MOSFET 结 -> 封装壳 -> TIM -> 驱动器散热基板 -> 关节外壳",
    ),
    (
        "mosfet_switching",
        "foc_inverter",
        0.10,
        "MOSFET 结 -> 封装壳 -> TIM -> 驱动器散热基板 -> 关节外壳",
    ),
    (
        "reducer_bearing",
        "drivetrain_and_control",
        0.15,
        "谐波减速器与轴承 -> 减速器壳体 -> 关节外壳",
    ),
    (
        "control_encoder",
        "drivetrain_and_control",
        0.05,
        "控制板与编码器 -> 安装位/内部空气 -> 关节外壳",
    ),
)


def simulate_foc_joint(inputs: FocJointInput) -> FocJointSimulationResult:
    """Allocate declared continuous and peak budgets across six heat sources."""

    sources = tuple(
        FocLossSource(
            id=source_id,
            group=group,
            continuous_w=inputs.continuous_loss_budget_w * share,
            peak_w=inputs.peak_loss_budget_w * share,
            heat_path=heat_path,
        )
        for source_id, group, share, heat_path in _LOSS_ALLOCATIONS
    )

    return FocJointSimulationResult(
        system=FocSystem(
            axes=inputs.axes,
            focus_joint=inputs.focus_joint,
            motor_type=inputs.motor_type,
        ),
        control=FocControl(
            dc_bus_voltage_v=inputs.dc_bus_voltage_v,
            modulation=inputs.modulation,
            current_loop_hz=inputs.current_loop_hz,
        ),
        loss_sources=sources,
        thermal_targets=FocThermalTargets(),
        total_continuous_loss_w=sum(source.continuous_w for source in sources),
        total_peak_loss_w=sum(source.peak_w for source in sources),
        loss_model="allocated_engineering_budget",
        is_first_principles=False,
        assumptions=(
            "各损耗源按工程热预算比例分配，需通过台架实测与参数标定修正。",
            "峰值工况沿用持续工况的损耗比例，未计入温度依赖和瞬态热容。",
        ),
        validation_tasks=(
            "用功率分析仪、测温元件和温升试验标定六类损耗源。",
            "将标定后的体积热源输入共轭传热 CFD，校核 MOSFET 壳温和绕组热点。",
        ),
    )


__all__ = [
    "FocControl",
    "FocJointInput",
    "FocJointSimulationResult",
    "FocLossSource",
    "FocSystem",
    "FocThermalTargets",
    "simulate_foc_joint",
]
