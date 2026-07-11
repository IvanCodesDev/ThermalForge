"""
ThermalForge 参数中枢 · 库条目层（LibraryEntry）

对应 parameter-schema-v0.1.md §2.5「库条目结构（预参数化后的开源案例）」。
短期 Demo 能跑通的前提：库里每个案例先转成和「上游输入层 + 参数中枢产出层」同构的字段，
这样用户输入和库案例才能在同一个 constraint_vector 空间里做最近邻检索。

本实现把「同构字段」具体化为：
- device_context: UserInput   —— 该案例适配的器件场景（同构于上游输入层）
- structure: dict             —— 该案例的结构几何参数（同构于结构生成层，落 leaf_vein/channel/flat）
- constraint_vector           —— 由 device_context 预计算的用户意图空间向量（与 UserInput.to_vector 同空间）
- model_path / preview_img / perf_notes —— 展示用（3D 模型路径、预览图、已知性能）

一物两用：constraint_vector 既做相似度匹配特征向量，又可作为长期 CadQuery 生成的上下文。
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List

from .user_input import UserInput


@dataclass
class LibraryEntry:
    """一个预参数化入库的散热结构案例。"""

    case_id: str
    source: str
    device_context: UserInput                      # 同构于上游输入层
    structure: Dict[str, Any]                       # 结构几何参数（含 structure_type）
    model_path: str = ""                            # 3D 模型文件路径（stl/step），展示用
    preview_img: str = ""                           # 预览图路径
    perf_notes: str = ""                            # 已知性能（温降/重量），增强展示说服力
    constraint_vector: List[float] = field(default_factory=list)  # 预计算意图向量

    def __post_init__(self):
        # 若未预计算，则由 device_context 派生，保证与 UserInput 同空间
        if not self.constraint_vector:
            self.constraint_vector = self.device_context.to_vector()

    @property
    def structure_type(self) -> str:
        return self.structure.get("structure_type", "leaf_vein")

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["structure_type"] = self.structure_type
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LibraryEntry":
        dc = UserInput.from_dict(d.get("device_context", {}))
        return cls(
            case_id=d["case_id"],
            source=d.get("source", ""),
            device_context=dc,
            structure=d.get("structure", {}),
            model_path=d.get("model_path", ""),
            preview_img=d.get("preview_img", ""),
            perf_notes=d.get("perf_notes", ""),
            constraint_vector=d.get("constraint_vector", []),
        )
