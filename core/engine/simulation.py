"""仿真后端抽象。

当前只提供 LumpedSimulationBackend（快速估算），不调用真实 ANSYS。
未来团队成员只需实现 SimulationBackend.evaluate_candidate()，即可把 SpaceClaim
建模脚本、Fluent/Mechanical 求解脚本或远程仿真服务接入优化器。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import Any, Dict

from .generator import generate
from .thermal import evaluate


@dataclass
class SimulationContext:
    power_w: float = 28.0
    t_ambient_c: float = 25.0
    t_limit_c: float = 80.0
    material: str = "AlSi10Mg"
    interface_r: float = 0.35
    source_model_path: str = ""
    preferred_flow_direction_deg: float | None = None


@dataclass
class SimulationOutcome:
    backend: str
    status: str
    t_hotspot_c: float
    mass_g: float
    pressure_drop_pa: float | None
    result: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SimulationBackend(ABC):
    """真实仿真适配器必须实现的最小契约。"""

    name = "abstract"

    @abstractmethod
    def evaluate_candidate(self, params: Any, context: SimulationContext) -> SimulationOutcome:
        raise NotImplementedError


class LumpedSimulationBackend(SimulationBackend):
    """开发期占位后端：用现有集总热阻模型快速筛选候选。"""

    name = "lumped_estimator"

    def evaluate_candidate(self, params: Any, context: SimulationContext) -> SimulationOutcome:
        _, stats = generate(params)
        medium = getattr(params, "cooling_medium", "air")
        result = evaluate(
            stats,
            power_w=context.power_w,
            t_ambient_c=context.t_ambient_c,
            t_limit_c=context.t_limit_c,
            material=context.material,
            medium=medium,
            interface_r=context.interface_r,
            structure_type=params.structure_type,
        )
        t_hotspot = result.t_hotspot_c
        direction_penalty = 0.0
        if context.preferred_flow_direction_deg is not None and hasattr(params, "flow_direction_deg"):
            delta = abs(float(params.flow_direction_deg) - context.preferred_flow_direction_deg) % 360.0
            delta = min(delta, 360.0 - delta)
            # 占位方向耦合项：偏离主散热/流动方向越多，估算温度越高。
            # 真实仿真接入后由 CFD 结果替代，不再使用该项。
            direction_penalty = 6.0 * (delta / 180.0) ** 2
            t_hotspot = round(t_hotspot + direction_penalty, 2)
        result_dict = result.to_dict()
        result_dict["t_hotspot_c_before_direction_penalty"] = result.t_hotspot_c
        result_dict["t_hotspot_c"] = t_hotspot
        result_dict["direction_penalty_c"] = round(direction_penalty, 3)
        result_dict["preferred_flow_direction_deg"] = context.preferred_flow_direction_deg
        return SimulationOutcome(
            backend=self.name,
            status="estimated",
            t_hotspot_c=t_hotspot,
            mass_g=result.mass_g,
            pressure_drop_pa=None,
            result=result_dict,
        )


class ExternalSimulationBackend(SimulationBackend):
    """未来真实仿真接口占位。

    团队可在此实现：
    1. 将 source_model_path 与 params 写入 SpaceClaim 脚本模板；
    2. 启动 ANSYS batch/远程任务；
    3. 解析热点温度、压降、质量等结果；
    4. 返回 SimulationOutcome。
    """

    name = "external_simulation"

    def __init__(self, endpoint: str = "", script_path: str = ""):
        self.endpoint = endpoint
        self.script_path = script_path

    def evaluate_candidate(self, params: Any, context: SimulationContext) -> SimulationOutcome:
        raise NotImplementedError(
            "真实仿真尚未接入。请由仿真团队实现 ExternalSimulationBackend.evaluate_candidate()"
        )
