"""
ThermalForge 参数 Schema（第一轮 v0.1）

对齐内部文档 annotation-strategy-v0.1.md 的字段定义：
- 叶脉热桥（leaf-vein heat bridge）
- 流道 / pin-fin（channel / pin-fin）
- 平板基线（flat baseline）

设计原则（参数即标签 parameter-as-label）：
每套参数都能唯一还原一张结构图；同时提供 to_vector() 归一化特征向量，
既用于相似度匹配，又用于下游 CAD 生成。

字段取值范围来自 annotation 文档，归一化统一到 [0,1]。
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any
import math


# ---- 归一化工具 ----
def _norm(x: float, lo: float, hi: float) -> float:
    """线性归一化到 [0,1]，越界裁剪。"""
    if hi <= lo:
        return 0.0
    return max(0.0, min(1.0, (x - lo) / (hi - lo)))


# 冷却介质分桶键（annotation 介质维度纠正后新增）
COOLING_MEDIUM = ("air", "liquid", "phase_change", "heat_pipe", "forced_air")
BOUNDARY_SHAPE = ("rect", "circle", "freeform")


@dataclass
class LeafVeinParams:
    """叶脉热桥：分形分支拓扑，擅长热点扩散。对应 §2.6 fish_scale_fin + topology。"""
    vein_archetype: str = "fractal_tree"   # pinnate / palmate / fractal_tree
    trunk_count: int = 1                   # 1-8 主干数
    branch_levels: int = 4                 # 1-6 分叉级数
    branch_angle: float = 35.0             # 15-75° 分叉角
    branch_ratio: float = 0.7              # 0.3-0.9 子/母通道宽比
    width_trunk: float = 3.0               # 0.5-5 mm 主干宽
    width_tip: float = 0.4                 # 0.1-1 mm 末梢宽
    length_scale: float = 60.0             # 10-200 mm 整体尺寸
    channel_depth: float = 3.0             # 0.5-10 mm 通道/筋条深
    density_gradient: float = 0.3          # 0-1 密度梯度
    tortuosity: float = 1.2                # 1.0-3.0 弯曲度
    symmetry: float = 0.8                  # 0-1 对称度
    porosity: float = 0.35                 # 0.1-0.6 覆盖率
    boundary_shape: str = "circle"         # rect / circle / freeform
    inlet_pos: float = 0.5                 # 0-1 进口相对位置
    outlet_pos: float = 0.5                # 0-1 出口相对位置
    flow_direction_deg: float = 90.0       # 0-360° 主叶脉/主流向方向
    cooling_medium: str = "air"            # 介质分桶键

    structure_type: str = field(default="leaf_vein", init=False)

    def to_vector(self) -> List[float]:
        return [
            _norm(self.trunk_count, 1, 8),
            _norm(self.branch_levels, 1, 6),
            _norm(self.branch_angle, 15, 75),
            _norm(self.branch_ratio, 0.3, 0.9),
            _norm(self.width_trunk, 0.5, 5),
            _norm(self.width_tip, 0.1, 1),
            _norm(self.length_scale, 10, 200),
            _norm(self.channel_depth, 0.5, 10),
            _norm(self.density_gradient, 0, 1),
            _norm(self.tortuosity, 1.0, 3.0),
            _norm(self.symmetry, 0, 1),
            _norm(self.porosity, 0.1, 0.6),
            _norm(self.inlet_pos, 0, 1),
            _norm(self.outlet_pos, 0, 1),
            _norm(self.flow_direction_deg, 0, 360),
            COOLING_MEDIUM.index(self.cooling_medium) / (len(COOLING_MEDIUM) - 1),
            BOUNDARY_SHAPE.index(self.boundary_shape) / (len(BOUNDARY_SHAPE) - 1),
        ]

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["structure_type"] = self.structure_type
        return d


@dataclass
class ChannelParams:
    """流道 / pin-fin：规则或优化流道。对应 §2.6 ventilation + topology。
    channel_pattern=='pinfin' 时为圆柱阵列（弱气流首选）。"""
    channel_pattern: str = "pinfin"        # parallel / serpentine / manifold / pinfin / topo_opt
    length_scale: float = 60.0             # 10-300 mm 结构占位边长(footprint)
    channel_width: float = 1.0             # 0.1-3 mm
    channel_height: float = 4.0            # 0.1-10 mm（pin 高）
    channel_pitch: float = 3.0             # 0.5-10 mm 间距
    channel_length: float = 60.0           # 10-300 mm
    channel_count: int = 36                # 1-200 通道/针数
    aspect_ratio: float = 4.0              # 0.1-20
    bend_radius: float = 3.0               # 1-50 mm（蛇形弯半径）
    serpentine_turns: int = 0              # 0-50
    manifold_type: str = "none"            # Z / U / tree / none
    wall_thickness: float = 0.8            # 0.1-5 mm
    topology_complexity: float = 0.2       # 0-1
    porosity: float = 0.5                  # 0.1-0.8
    boundary_shape: str = "rect"           # rect / circle / freeform
    inlet_outlet_config: str = "opp_side"  # same_side / opp_side / manifold
    cooling_medium: str = "air"            # 介质分桶键

    structure_type: str = field(default="channel", init=False)

    def to_vector(self) -> List[float]:
        patterns = ("parallel", "serpentine", "manifold", "pinfin", "topo_opt")
        return [
            patterns.index(self.channel_pattern) / (len(patterns) - 1),
            _norm(self.length_scale, 10, 300),
            _norm(self.channel_width, 0.1, 3),
            _norm(self.channel_height, 0.1, 10),
            _norm(self.channel_pitch, 0.5, 10),
            _norm(self.channel_length, 10, 300),
            _norm(self.channel_count, 1, 200),
            _norm(self.aspect_ratio, 0.1, 20),
            _norm(self.bend_radius, 1, 50),
            _norm(self.serpentine_turns, 0, 50),
            _norm(self.wall_thickness, 0.1, 5),
            _norm(self.topology_complexity, 0, 1),
            _norm(self.porosity, 0.1, 0.8),
            COOLING_MEDIUM.index(self.cooling_medium) / (len(COOLING_MEDIUM) - 1),
            BOUNDARY_SHAPE.index(self.boundary_shape) / (len(BOUNDARY_SHAPE) - 1),
        ]

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["structure_type"] = self.structure_type
        return d


@dataclass
class FlatBaselineParams:
    """平板基线：对照组（PDF §6.3 基线）。仅几块尺寸参数。"""
    length_scale: float = 60.0     # mm
    channel_depth: float = 3.0     # mm（板厚）
    boundary_shape: str = "rect"
    cooling_medium: str = "air"

    structure_type: str = field(default="flat", init=False)

    def to_vector(self) -> List[float]:
        return [
            _norm(self.length_scale, 10, 200),
            _norm(self.channel_depth, 0.5, 10),
            BOUNDARY_SHAPE.index(self.boundary_shape) / (len(BOUNDARY_SHAPE) - 1),
            COOLING_MEDIUM.index(self.cooling_medium) / (len(COOLING_MEDIUM) - 1),
        ]

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["structure_type"] = self.structure_type
        return d


def from_dict(d: Dict[str, Any]):
    """按 structure_type 反序列化为对应 dataclass（忽略未知字段）。"""
    st = d.get("structure_type", "leaf_vein")
    cls = {"leaf_vein": LeafVeinParams, "channel": ChannelParams, "flat": FlatBaselineParams}[st]
    valid = {k: v for k, v in d.items() if k in cls.__annotations__ and k != "structure_type"}
    return cls(**valid)


# ---- 字段范围表（供 JSON Schema 导出 / 校验复用）----
# 每项：(min, max) 连续范围，或 [..] 枚举列表
RANGE_SPECS: Dict[str, Dict[str, Any]] = {
    "leaf_vein": {
        "vein_archetype": ["pinnate", "palmate", "fractal_tree"],
        "trunk_count": (1, 8),
        "branch_levels": (1, 6),
        "branch_angle": (15, 75),
        "branch_ratio": (0.3, 0.9),
        "width_trunk": (0.5, 5),
        "width_tip": (0.1, 1),
        "length_scale": (10, 200),
        "channel_depth": (0.5, 10),
        "density_gradient": (0, 1),
        "tortuosity": (1.0, 3.0),
        "symmetry": (0, 1),
        "porosity": (0.1, 0.6),
        "boundary_shape": ["rect", "circle", "freeform"],
        "inlet_pos": (0, 1),
        "outlet_pos": (0, 1),
        "flow_direction_deg": (0, 360),
        "cooling_medium": ["air", "liquid", "phase_change", "heat_pipe", "forced_air"],
    },
    "channel": {
        "channel_pattern": ["parallel", "serpentine", "manifold", "pinfin", "topo_opt"],
        "length_scale": (10, 300),
        "channel_width": (0.1, 3),
        "channel_height": (0.1, 10),
        "channel_pitch": (0.5, 10),
        "channel_length": (10, 300),
        "channel_count": (1, 200),
        "aspect_ratio": (0.1, 20),
        "bend_radius": (1, 50),
        "serpentine_turns": (0, 50),
        "manifold_type": ["Z", "U", "tree", "none"],
        "wall_thickness": (0.1, 5),
        "topology_complexity": (0, 1),
        "porosity": (0.1, 0.8),
        "boundary_shape": ["rect", "circle", "freeform"],
        "inlet_outlet_config": ["same_side", "opp_side", "manifold"],
        "cooling_medium": ["air", "liquid", "phase_change", "heat_pipe", "forced_air"],
    },
    "flat": {
        "length_scale": (10, 200),
        "channel_depth": (0.5, 10),
        "boundary_shape": ["rect", "circle", "freeform"],
        "cooling_medium": ["air", "liquid", "phase_change", "heat_pipe", "forced_air"],
    },
}

STRUCTURE_CLASSES = {
    "leaf_vein": LeafVeinParams,
    "channel": ChannelParams,
    "flat": FlatBaselineParams,
}
