"""
ThermalForge 参数中枢 · 上游输入层（UserInput）

对应 parameter-schema-v0.1.md §1「上游输入层」+ §2.6 具身结构级意图。
这是连接「理解层（照片/自然语言→参数）」与「生成层（结构/CAD）」的契约输入：
用户给出的器件信息 → 归一化为「用户意图空间约束向量」(constraint_vector 的 intent 部分)，
与库案例（LibraryEntry）在同一个 23 维空间里做最近邻检索，实现「用户输入 ↔ 库案例」同空间匹配。

设计要点（一物两用）：
- to_vector() 既用于相似度匹配，也作为长期 CadQuery 生成时选择结构模板的偏好信号。
- 派生 thermal_load（热流密度）= power_w / 体积，衡量多烫。
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List

# ---- 枚举（与 parameter-schema-v0.1.md §1 对齐）----
DEVICE_TYPES = ("关节电机", "Jetson/边缘计算盒", "MOSFET/驱动器", "传感器舱", "灵巧手模组",
               "无人机动力电机", "无人机电调", "工业变频器", "医疗激光模块")
MATERIALS = ("铝1060", "铝6061", "铜", "钢", "工程塑料", "PCB基材")
MANUFACTURING = ("3D打印", "CNC", "钣金", "CNC+3D打印")
# 冷却介质（与 schema.py 同键，便于意图→结构映射）
MEDIUM = ("air", "liquid", "phase_change", "heat_pipe", "forced_air")

# 归一化范围（连续字段）
_TEMP_RANGE = (25.0, 120.0)      # 温度类（max_temp_c / ambient_temp_c）
_POWER_RANGE = (0.5, 200.0)      # 功耗 W
_WEIGHT_RANGE = (1.0, 500.0)     # 重量 g
_LOAD_RANGE = (0.0, 0.05)        # 热流密度 W/mm^3


def _norm(x: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 0.0
    return max(0.0, min(1.0, (x - lo) / (hi - lo)))


def _onehot(value: str, domain: tuple) -> List[float]:
    return [1.0 if value == d else 0.0 for d in domain]


@dataclass
class UserInput:
    """用户/上游给出的器件与约束信息（参数中枢契约输入）。"""

    device_type: str = "关节电机"          # DEVICE_TYPES
    dimensions: Dict[str, float] = field(
        default_factory=lambda: {"length_mm": 60.0, "width_mm": 60.0, "height_mm": 40.0}
    )
    power_w: float = 28.0                   # 功耗 W
    max_temp_c: float = 80.0                # 允许最高温度 ℃
    material: str = "铝6061"                # MATERIALS
    has_fan: bool = False                   # 是否强制风冷
    max_weight_g: float = 60.0              # 重量上限 g
    manufacturing: str = "3D打印"           # MANUFACTURING
    ambient_temp_c: float = 25.0            # 环境温度 ℃

    # ---- 体积与热负载派生 ----
    def volume_mm3(self) -> float:
        d = self.dimensions
        if "outer_dia_mm" in d or "inner_dia_mm" in d:
            outer = d.get("outer_dia_mm", 60.0)
            inner = d.get("inner_dia_mm", 30.0)
            h = d.get("height_mm", 40.0)
            return 3.14159265 * ((outer / 2.0) ** 2 - (inner / 2.0) ** 2) * h
        l = d.get("length_mm", 60.0)
        w = d.get("width_mm", 60.0)
        h = d.get("height_mm", 40.0)
        return l * w * h

    def thermal_load(self) -> float:
        """热流密度 W/mm^3，衡量多烫。"""
        v = self.volume_mm3()
        return self.power_w / v if v > 0 else 0.0

    def preferred_medium(self) -> str:
        """由意图派生首选冷却介质：热负载高或温度余量小 → 倾向液冷/相变，否则气冷。"""
        headroom = self.max_temp_c - self.ambient_temp_c
        if self.has_fan:
            # 有风扇 / 螺旋桨洗流 → 强制风冷（forced_air，高 h）
            return "forced_air"
        if self.thermal_load() > 0.012 or headroom < 35:
            # 高载或余量紧 → 液冷 / 相变优先
            return "liquid"
        return "air"

    # ---- 校验 ----
    def validate(self) -> List[str]:
        errs = []
        if self.device_type not in DEVICE_TYPES:
            errs.append(f"device_type 须为 {DEVICE_TYPES}")
        if self.material not in MATERIALS:
            errs.append(f"material 须为 {MATERIALS}")
        if self.manufacturing not in MANUFACTURING:
            errs.append(f"manufacturing 须为 {MANUFACTURING}")
        if self.power_w <= 0:
            errs.append("power_w 须 > 0")
        if not (0 < self.max_temp_c <= 300):
            errs.append("max_temp_c 须在 (0, 300]")
        if self.max_weight_g <= 0:
            errs.append("max_weight_g 须 > 0")
        if not self.dimensions:
            errs.append("dimensions 不能为空")
        return errs

    # ---- 用户意图空间约束向量（23 维，固定顺序）----
    # 顺序：device(5) + material(6) + manufacturing(3) + has_fan(1)
    #      + thermal_load(1) + temp_headroom(1) + max_weight(1) + ambient(1) + medium(4)
    def to_vector(self) -> List[float]:
        headroom = self.max_temp_c - self.ambient_temp_c
        vec = []
        vec += _onehot(self.device_type, DEVICE_TYPES)        # 5
        vec += _onehot(self.material, MATERIALS)              # 6
        vec += _onehot(self.manufacturing, MANUFACTURING)     # 3
        vec.append(1.0 if self.has_fan else 0.0)              # 1
        vec.append(_norm(self.thermal_load(), *_LOAD_RANGE))  # 1
        vec.append(_norm(headroom, 5.0, 95.0))                # 1
        vec.append(_norm(self.max_weight_g, *_WEIGHT_RANGE))  # 1
        vec.append(_norm(self.ambient_temp_c, *_TEMP_RANGE))  # 1
        vec += _onehot(self.preferred_medium(), MEDIUM)       # 4
        return vec

    @staticmethod
    def vector_spec() -> List[Dict[str, Any]]:
        """返回约束向量各维度的说明（供文档/JSON Schema/前端对齐）。"""
        spec = []
        for d in DEVICE_TYPES:
            spec.append({"block": "device_type", "field": d, "type": "onehot"})
        for m in MATERIALS:
            spec.append({"block": "material", "field": m, "type": "onehot"})
        for m in MANUFACTURING:
            spec.append({"block": "manufacturing", "field": m, "type": "onehot"})
        spec.append({"block": "has_fan", "field": "has_fan", "type": "binary"})
        spec.append({"block": "thermal_load", "field": "thermal_load_W_per_mm3", "type": "norm", "range": list(_LOAD_RANGE)})
        spec.append({"block": "temp_headroom", "field": "max_temp_c-ambient_c", "type": "norm", "range": [5.0, 95.0]})
        spec.append({"block": "max_weight", "field": "max_weight_g", "type": "norm", "range": list(_WEIGHT_RANGE)})
        spec.append({"block": "ambient", "field": "ambient_temp_c", "type": "norm", "range": list(_TEMP_RANGE)})
        for m in MEDIUM:
            spec.append({"block": "preferred_medium", "field": f"medium:{m}", "type": "onehot"})
        return spec

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "UserInput":
        valid = {k: v for k, v in d.items() if k in cls.__annotations__}
        return cls(**valid)
